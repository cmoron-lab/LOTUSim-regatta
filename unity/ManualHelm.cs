// Copyright (c) 2026 Cyril Moron — EPL-2.0
// Manual helm: keyboard always works; any two physical axes (rudder pedals,
// HOTAS, a gamepad stick) bind in-game with [B]. [M] or gamepad Start toggles
// MANUAL. Commands go out as the same VesselCmdArray JSON the helmsman
// publishes — on /<world>/manual_cmd_array, where a fresh manual message
// overrides the Pilot and silence hands the helm back (dead-man switch).
//
// Binding is by EXCURSION from rest: push the control, the axis that moved
// the most wins, its direction and travel are recorded, PlayerPrefs keeps it.
// A phantom axis parked at an extreme (Oculus virtual pad, an idle throttle)
// can never be selected — it does not move. Axes are read through the new
// Input System, one control on one device: no cross-device "furthest from
// zero wins" contest, which is what jammed the legacy Horizontal/Vertical
// here (a HOTAS at rest pinned them, and the keyboard lost every frame).
//
// Feel: the helm is positional (pedal deflection = rudder angle, sprung by
// the hardware); the sheet is a ratchet (deflection = ease/haul RATE, so a
// sprung stick can let go and the trim stays). Keyboard: arrows, same idea.
using System.Collections.Generic;
using RosMessageTypes.Lotusim;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.Controls;

public class ManualHelm : MonoBehaviour
{
    public string worldName = "lotusim";
    public string vesselName = "focus_v2";
    public float publishHz = 30f;      // the helmsman consumes at 30 Hz; faster is wasted
    public float helmMaxDeg = 35f;     // the harness clamp; commanding past it does nothing
    public float helmSlewDegS = 150f;  // keyboard helm: hard over at RC-servo pace
    public float helmExpo = 1.5f;      // RC-style expo: softer near centre, same max
    public float deadzone = 0.10f;     // fraction of the calibrated travel
    public float sheetMinDeg = 4f;     // the sail model's floor (see pilot.opt_sheet)
    public float sheetMaxDeg = 80f;
    public float sheetSlewDegS = 120f; // full range in ~0.6 s at full deflection
    // ON for an axis that HOLDS its position (the Warthog throttle): the axis IS
    // the sheet position, full push = hauled in -- a mainsheet traveler, as
    // direct as the pedals. OFF for a sprung stick, where absolute mapping would
    // snap the sheet back to centre on release: there the axis is a ratchet RATE.
    public bool sheetPositional = false;
    // Ratchet flavour, the helmsman's pick: push the stick toward the side the
    // boom is on to ease it out, toward the centreline to haul it in. The sail
    // goes where the stick sends it, on either tack. OFF = fixed convention
    // (stick right always hauls), which "inverts" on screen at every tack.
    public bool sheetFollowsBoom = true;

    bool _manual;
    ActuatorAnimator _boat;            // boom side lives there; spawns late
    float _helmDeg, _sheetDeg = 20f;   // a close-hauled-ish sheet to start from
    float _nextPub;
    ROSConnection _ros;
    string _topic;

    // ---- bound axes -------------------------------------------------------
    class Axis
    {
        public AxisControl ctrl;
        public string path;
        public float rest, sign, span;

        // Normalised deflection: +1 = the direction pushed during binding.
        public float Norm(float dz)
        {
            if (ctrl == null) return 0f;
            float n = (ctrl.ReadValue() - rest) * sign / span;
            return Mathf.Abs(n) < dz ? 0f : Mathf.Clamp(n, -1f, 1f);
        }
    }

    // _helmL exists for pedals of the toe-brake kind: two independent one-sided
    // axes, one per side. Unbound (single bidirectional helm axis) it stays null.
    readonly Axis _helm = new Axis(), _helmL = new Axis(), _sheet = new Axis();

    enum Cal { Off, HelmR, HelmL, Sheet }
    Cal _cal = Cal.Off;
    Dictionary<AxisControl, float> _rest;
    double _settleAt, _armAt;
    bool _armed;

    void Start()
    {
        _topic = $"/{worldName}/manual_cmd_array";
        _ros = ROSConnection.GetOrCreateInstance();
        _ros.RegisterPublisher<VesselCmdArrayMsg>(_topic);
        Load("helm", _helm, "/Thrustmaster T-Rudder/stick/x");    // right toe brake, 0->1
        Load("helmL", _helmL, "/Thrustmaster T-Rudder/stick/y");  // left toe brake, 0->1
        // "Thustmaster" sic: the Warthog reports its own name with the typo, and
        // the path must match the device, not the dictionary.
        Load("sheet", _sheet, "/Thustmaster Joystick - HOTAS Warthog/stick/x");
        // A fresh player enumerates devices AFTER scene Start (the editor has had
        // them for ages), so a one-shot resolve here misses them: re-resolve on
        // every device arrival, and log an inventory the Player.log can answer
        // "what is this control actually called on this side" with.
        InputSystem.onDeviceChange += OnDeviceChange;
        foreach (var d in InputSystem.devices)
            Debug.Log($"[ManualHelm] device: {d.name} ({d.layout})");
        // The HUD bootstraps itself: an add-the-component step gets forgotten
        // between editor and player scenes, and did.
        if (FindObjectOfType<RegattaHud>() == null)
            gameObject.AddComponent<RegattaHud>();
    }

    void OnDestroy()
    {
        InputSystem.onDeviceChange -= OnDeviceChange;
    }

    void OnDeviceChange(InputDevice device, InputDeviceChange change)
    {
        if (change != InputDeviceChange.Added && change != InputDeviceChange.Reconnected)
            return;
        Debug.Log($"[ManualHelm] device {change}: {device.name} ({device.layout})");
        foreach (var a in new[] { _helm, _helmL, _sheet })
            if (a.ctrl == null) Resolve(a);
    }

    static void Resolve(Axis a)
    {
        if (string.IsNullOrEmpty(a.path)) return;
        using (var hits = InputSystem.FindControls(a.path))
            if (hits.Count > 0) a.ctrl = hits[0] as AxisControl;
        Debug.Log($"[ManualHelm] resolve {a.path} -> {(a.ctrl == null ? "MISS" : "ok")}");
    }

    void Update()
    {
        if (Input.GetKeyDown(KeyCode.B) && _cal == Cal.Off)
        {
            _cal = Cal.HelmR;
            BeginPhase();
        }
        if (_cal != Cal.Off)
        {
            // No publishing while binding: the dead-man switch hands the boat to
            // the algorithm, which sails it for you until you are done.
            if (Input.GetKeyDown(KeyCode.Escape)) _cal = Cal.Off;
            else RunCalibration();
            return;
        }

        // M (QWERTY), Semicolon (an AZERTY M arrives as that -- legacy Input maps
        // by QWERTY position), or Start on a REAL gamepad. Not legacy
        // JoystickButton7: that means "button 7 on any joystick", and one of the
        // Warthog's triggers lands exactly there -- squeezing it silently handed
        // the boat back to the algorithm. Gamepad excludes HID joysticks.
        if (Input.GetKeyDown(KeyCode.M) || Input.GetKeyDown(KeyCode.Semicolon)
            || (Gamepad.current != null && Gamepad.current.startButton.wasPressedThisFrame))
            _manual = !_manual;
        if (!_manual) return;

        // Keyboard first -- keys cannot be pinned by any device. Left = turn to
        // port = POSITIVE helm (measured convention, reference.md).
        float kb = (Input.GetKey(KeyCode.LeftArrow) ? 1f : 0f)
                 - (Input.GetKey(KeyCode.RightArrow) ? 1f : 0f);
        // "Rightness": one bidirectional axis reads as-is; toe-brake pedals read
        // as right-press minus left-press, each one-sided.
        float hj = _helmL.ctrl == null
            ? _helm.Norm(deadzone)
            : Mathf.Clamp01(_helm.Norm(deadzone)) - Mathf.Clamp01(_helmL.Norm(deadzone));
        hj = Mathf.Sign(hj) * Mathf.Pow(Mathf.Abs(hj), helmExpo);
        if (kb != 0f)
            _helmDeg = Mathf.MoveTowards(_helmDeg, kb * helmMaxDeg, helmSlewDegS * Time.deltaTime);
        else if (hj != 0f)
            _helmDeg = -hj * helmMaxDeg;  // positional: deflection = rudder angle
        else
            _helmDeg = Mathf.MoveTowards(_helmDeg, 0f, helmSlewDegS * Time.deltaTime);

        // Sheet. The bound axis's + direction = pushed RIGHT at binding.
        // Positional (throttle): deflection = sheet position, slew-limited for
        // the winch feel. Ratchet (stick): deflection = ease/haul rate -- and
        // with sheetFollowsBoom the sign follows the boom's side, so the stick
        // pushes the sail where it points on either tack. The keyboard (down
        // eases out) keeps the fixed convention; no side confusion was ever
        // reported on keys.
        float dir = (Input.GetKey(KeyCode.DownArrow) ? 1f : 0f)
                  - (Input.GetKey(KeyCode.UpArrow) ? 1f : 0f);
        float sj = _sheet.Norm(deadzone);
        if (sheetPositional && _sheet.ctrl != null && dir == 0f)
            _sheetDeg = Mathf.MoveTowards(_sheetDeg,
                Mathf.Lerp(sheetMaxDeg, sheetMinDeg, Mathf.Clamp01(sj)),
                2f * sheetSlewDegS * Time.deltaTime);
        else
        {
            if (_boat == null) _boat = FindObjectOfType<ActuatorAnimator>();
            // -1 keeps the fixed "+ hauls" convention when not following the boom.
            float side = (sheetFollowsBoom && _boat != null) ? _boat.BoomSide : -1f;
            _sheetDeg = Mathf.Clamp(
                _sheetDeg + (dir != 0f ? dir : sj * side) * sheetSlewDegS * Time.deltaTime,
                sheetMinDeg, sheetMaxDeg);
        }

        // Feed the animator the local command every frame: the boom follows the
        // hand, not the jittery round trip (see ActuatorAnimator.SetLocalCmd).
        if (_boat == null) _boat = FindObjectOfType<ActuatorAnimator>();
        if (_boat != null) _boat.SetLocalCmd(_sheetDeg, _helmDeg);

        // Publish even with no input held: a centred rudder is still a command,
        // and the stream is what keeps the dead-man switch on our side.
        if (Time.time < _nextPub) return;
        _nextPub = Time.time + 1f / publishHz;
        // Concatenation, not string.Format: composite formatting parses a trailing
        // "{1:F4}}}" with the escaped-brace rule first, and the helm arrives as the
        // literal text F4 -- every frame then dies in the helmsman's json.loads.
        // InvariantCulture: a French locale would print 0,35 and kill it too.
        var inv = System.Globalization.CultureInfo.InvariantCulture;
        var cmd = new VesselCmdMsg
        {
            vessel_name = vesselName,
            cmd_string = "{\"mainsail(sheet)\": "
                + (_sheetDeg * Mathf.Deg2Rad).ToString("F4", inv)
                + ", \"rudder(helm)\": "
                + (_helmDeg * Mathf.Deg2Rad).ToString("F4", inv) + "}",
        };
        _ros.Publish(_topic, new VesselCmdArrayMsg { cmds = new[] { cmd } });
    }

    // ---- binding ----------------------------------------------------------
    static IEnumerable<AxisControl> Candidates()
    {
        foreach (var d in InputSystem.devices)
        {
            if (d is Keyboard || d is Mouse || d is Pointer || d is Sensor) continue;
            foreach (var c in d.allControls)
                if (c is AxisControl a && !(c is ButtonControl) && !c.synthetic && !c.noisy)
                    yield return a;
        }
    }

    void BeginPhase()
    {
        // Rest is snapshot 0.6 s into the phase, not at its start: the control
        // held through the PREVIOUS phase is still deflected when this one
        // begins, and releasing it would otherwise read as this phase's push.
        _armAt = Time.timeAsDouble + 0.6;
        _armed = false;
        _settleAt = 0;
    }

    void RunCalibration()
    {
        const float TRIGGER = 0.35f;  // excursion that starts the settle window
        const double SETTLE = 1.2;    // seconds to keep holding the control

        if (!_armed)
        {
            if (Time.timeAsDouble < _armAt) return;
            _rest = new Dictionary<AxisControl, float>();
            foreach (var c in Candidates()) _rest[c] = c.ReadValue();
            _armed = true;
            return;
        }
        if (_settleAt == 0)
        {
            foreach (var kv in _rest)
                if (Mathf.Abs(kv.Key.ReadValue() - kv.Value) > TRIGGER)
                {
                    _settleAt = Time.timeAsDouble + SETTLE;
                    break;
                }
            return;
        }
        if (Time.timeAsDouble < _settleAt) return;

        // Phase over: whatever is deflected the most right now, held, wins.
        AxisControl best = null;
        float bestExc = 0f;
        foreach (var kv in _rest)
        {
            float e = Mathf.Abs(kv.Key.ReadValue() - kv.Value);
            if (e > bestExc) { bestExc = e; best = kv.Key; }
        }
        if (!CalibrationCandidateIsHeld(bestExc, TRIGGER))
        {
            _settleAt = 0;
            return;
        }
        var ax = _cal == Cal.HelmR ? _helm : _cal == Cal.HelmL ? _helmL : _sheet;
        if (_cal == Cal.HelmL && best == _helm.ctrl)
        {
            // Same control pushed the other way: a single bidirectional helm
            // axis (a stick, a differential pedal slide). No left binding.
            ax.ctrl = null;
        }
        else
        {
            ax.ctrl = best;
            ax.rest = _rest[best];
            ax.sign = Mathf.Sign(best.ReadValue() - ax.rest);
            ax.span = Mathf.Max(0.2f, bestExc);  // floor: a sliver of travel is noise
        }
        Save(_cal == Cal.HelmR ? "helm" : _cal == Cal.HelmL ? "helmL" : "sheet", ax);
        _cal = _cal == Cal.HelmR ? Cal.HelmL : _cal == Cal.HelmL ? Cal.Sheet : Cal.Off;
        if (_cal != Cal.Off) BeginPhase();
    }

    static void Save(string key, Axis a)
    {
        PlayerPrefs.SetString($"regatta.{key}.path", a.ctrl == null ? "" : a.ctrl.path);
        PlayerPrefs.SetFloat($"regatta.{key}.rest", a.rest);
        PlayerPrefs.SetFloat($"regatta.{key}.sign", a.sign);
        PlayerPrefs.SetFloat($"regatta.{key}.span", a.span);
        PlayerPrefs.Save();
    }

    static void Load(string key, Axis a, string defaultPath)
    {
        string pathKey = $"regatta.{key}.path";
        bool saved = PlayerPrefs.HasKey(pathKey);
        a.path = PlayerPrefs.GetString(pathKey, "");
        a.rest = PlayerPrefs.GetFloat($"regatta.{key}.rest", 0f);
        a.sign = PlayerPrefs.GetFloat($"regatta.{key}.sign", 1f);
        a.span = PlayerPrefs.GetFloat($"regatta.{key}.span", 1f);
        // Empty is deliberate for the unused second side of a bidirectional
        // helm. It must survive restart instead of reviving the baked pedal.
        if (saved && a.path == "")
        {
            a.ctrl = null;
            return;
        }
        // A persisted binding with sign or span 0 is corrupt, not a choice --
        // float persistence proved unreliable here (registry read them back as
        // zeroes) -- so fall back to the baked-in default: rest 0, sign +1,
        // span 1 fits a 0->1 toe brake and a centred -1..1 stick alike.
        if (ShouldUseDefaultBinding(
            saved, a.path, a.sign, a.span))
        {
            a.path = defaultPath;
            a.rest = 0f; a.sign = 1f; a.span = 1f;
        }
        Resolve(a);
    }

    static bool CalibrationCandidateIsHeld(
        float excursion, float trigger) => excursion > trigger;

    static bool ShouldUseDefaultBinding(
        bool saved, string path, float sign, float span) =>
        !saved || (path != "" && (sign == 0f || span <= 0f));

    // ---- HUD --------------------------------------------------------------
    void OnGUI()
    {
        string line;
        if (_cal == Cal.HelmR)
            line = "[B] binding 1/3 -- push your HELM control hard RIGHT and hold... (Esc aborts)";
        else if (_cal == Cal.HelmL)
            line = "[B] binding 2/3 -- release, then HELM hard LEFT and hold"
                 + " (same control the other way if it is one axis)...";
        else if (_cal == Cal.Sheet)
            line = "[B] binding 3/3 -- release, then SHEET control to the RIGHT"
                 + " (or full forward on a throttle) and hold...";
        else if (_manual)
            line = $"[M/Start] helm: MANUAL  helm {_helmDeg,4:F0} deg  sheet {_sheetDeg,3:F0} deg"
                 + $"  ({Name(_helm)} / {Name(_sheet)} / arrows; B rebinds)";
        else
            line = "[M/Start] helm: AUTO -- the algorithm sails  (M or Start takes the helm)";
        // y=94: below the ROS-TCP connection HUD (top-left) and the camera line.
        GUI.Label(new Rect(10, 94, 760, 24), line);
    }

    static string Name(Axis a) => a.ctrl == null ? "unbound" : a.ctrl.device.displayName;
}
