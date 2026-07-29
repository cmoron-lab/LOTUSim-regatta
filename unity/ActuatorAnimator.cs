// Copyright (c) 2026 Cyril Moron — EPL-2.0
// Animates the focus_v2 sail (Boom+Mainsail) and rudder from the live
// /<world>/vessel_cmd_array commands. Attach to the focus_v2 PREFAB ROOT —
// parts are found by name, no manual wiring.
//
// Sail side: the boom falls to leeward. The tack is derived geometrically
// (world bearing of BowNose relative to Hull, against a constant wind from
// world +Z / north), so no frame-convention assumption is baked in. During a
// tack the sign flips as the bow crosses the wind and the slew rate sweeps
// the boom across — which is what a real tack looks like.
//
// The Inspector sign knobs (sailSign/rudderSign) exist to flip a convention
// live at first visual check instead of recompiling.
using System.Text.RegularExpressions;
using RosMessageTypes.Lotusim;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;

public class ActuatorAnimator : MonoBehaviour
{
    public string worldName = "lotusim";
    public string vesselName = "focus_v2";
    public float sailSlew = 90f;     // deg/s
    public float rudderSlew = 180f;  // deg/s
    public float sailSign = 1f;      // flip live if the boom sits to windward
    public float rudderSign = 1f;    // flip live if the rudder kicks the wrong way
    public float windFromDeg = 0f;
    public float windSpeed = 3f;
    public float maxPoseStep = 0.25f;
    public float velocitySmoothing = 0.15f;
    public float tackLuffTime = 0.65f;
    public float flutterHz = 4f;

    static readonly Regex SheetRe = new Regex(@"""mainsail\(sheet\)""\s*:\s*(-?[\d.eE+-]+)");
    static readonly Regex HelmRe = new Regex(@"""rudder\(helm\)""\s*:\s*(-?[\d.eE+-]+)");

    Transform _boom, _mainsail, _jib, _rudder, _hull, _bow;
    SkinnedMeshRenderer _mainsailRenderer, _jibRenderer;
    int[] _mainsailShapes, _jibShapes;
    float _sheetDeg, _helmDeg;       // latest commanded magnitudes (deg)
    float _sailAngle, _rudderAngle;  // currently displayed local Y angles (deg)
    Vector3 _lastPosition, _boatVelocity;
    float _lastStableSide = 1f, _tackLuffAge, _flutterPhase;
    bool _hasStableSide;
    Quaternion _boomRest, _sailRest, _rudderRest;

    static readonly string[] SailShapeNames = {
        "FilledPort", "FilledStarboard", "RipplePort", "RippleStarboard"
    };

    // Read by WakeEmitter: spares a second subscription and a duplicate parse.
    public float RudderAngle => _rudderAngle;

    // Read by RegattaCameraRig: the hull's bow axis (Hull -> BowNose), flattened.
    // Convention-free like the sail-side test below; zero until the parts exist.
    public Vector3 BowAxis
    {
        get
        {
            if (!_hull || !_bow) return Vector3.zero;
            Vector3 f = _bow.position - _hull.position;
            f.y = 0f;
            return f.sqrMagnitude > 1e-6f ? f.normalized : Vector3.zero;
        }
    }

    void Start()
    {
        _boom = FindPart("Boom");
        _mainsail = FindPart("Mainsail");
        _jib = FindPart("Jib");
        _rudder = FindPart("Rudder");
        _hull = FindPart("Hull");
        _bow = FindPart("BowNose");
        _lastPosition = transform.position;
        _tackLuffAge = tackLuffTime;
        ResolveSailShapes(_mainsail, "Mainsail", out _mainsailRenderer, out _mainsailShapes);
        ResolveSailShapes(_jib, "Jib", out _jibRenderer, out _jibShapes);
        if (_boom) _boomRest = _boom.localRotation;
        if (_mainsail) _sailRest = _mainsail.localRotation;
        if (_rudder) _rudderRest = _rudder.localRotation;
        ROSConnection.GetOrCreateInstance()
            .Subscribe<VesselCmdArrayMsg>($"/{worldName}/vessel_cmd_array", OnCmd);
    }

    void OnCmd(VesselCmdArrayMsg msg)
    {
        foreach (var c in msg.cmds)
        {
            if (!string.IsNullOrEmpty(c.vessel_name) && c.vessel_name != vesselName)
                continue;
            var sheet = SheetRe.Match(c.cmd_string);
            var helm = HelmRe.Match(c.cmd_string);
            if (sheet.Success) _sheetDeg = float.Parse(sheet.Groups[1].Value,
                System.Globalization.CultureInfo.InvariantCulture) * Mathf.Rad2Deg;
            if (helm.Success) _helmDeg = float.Parse(helm.Groups[1].Value,
                System.Globalization.CultureInfo.InvariantCulture) * Mathf.Rad2Deg;
        }
    }

    // Read by ManualHelm's boom-side sheet mapping: +1 = boom to starboard.
    public float BoomSide { get; private set; } = 1f;

    float _ovrSheetDeg, _ovrHelmDeg, _ovrAt = -1f;

    // ManualHelm feeds its LOCAL command here every frame while manual: the boom
    // then follows the hand instead of the Unity->WSL->helmsman round trip, whose
    // 30 Hz beats against this side's 30 Hz and clumps into visible jerks. The
    // physics still gets the round trip; only the rendering takes the shortcut --
    // and this animator was already rendering the command, never the simulation.
    public void SetLocalCmd(float sheetDeg, float helmDeg)
    {
        _ovrSheetDeg = sheetDeg;
        _ovrHelmDeg = helmDeg;
        _ovrAt = Time.time;
    }

    void Update()
    {
        Vector3 delta = transform.position - _lastPosition;
        _lastPosition = transform.position;
        delta.y = 0f;
        if (delta.magnitude > maxPoseStep)
            _boatVelocity = Vector3.zero;
        else
            _boatVelocity = Vector3.Lerp(
                _boatVelocity,
                Time.deltaTime > 0f ? delta / Time.deltaTime : Vector3.zero,
                velocitySmoothing > 0f
                    ? Mathf.Clamp01(Time.deltaTime / velocitySmoothing)
                    : 1f);

        Vector3 trueAir = Quaternion.Euler(0f, windFromDeg, 0f)
            * Vector3.back * windSpeed;
        Vector3 apparent = SailVisualMath.ApparentWind(trueAir, _boatVelocity);
        Vector3 windFrom = apparent.sqrMagnitude > 1e-6f
            ? -apparent.normalized
            : Vector3.zero;
        Vector3 bowAxis = BowAxis;
        float side = _lastStableSide;
        float windAngle = 0f;
        if (windFrom != Vector3.zero && bowAxis != Vector3.zero)
        {
            windAngle = Vector3.SignedAngle(windFrom, bowAxis, Vector3.up);
            if (Mathf.Abs(windAngle) > 5f)
            {
                float stableSide = SailVisualMath.StableSide(
                    windAngle, _lastStableSide);
                if (_hasStableSide && stableSide != _lastStableSide)
                    _tackLuffAge = 0f;
                _lastStableSide = stableSide;
                _hasStableSide = true;
                side = stableSide;
            }
        }
        BoomSide = side;

        float sheetDeg = _sheetDeg, helmDeg = _helmDeg;
        if (_ovrAt >= 0f && Time.time - _ovrAt < 0.3f)
        {
            sheetDeg = _ovrSheetDeg;
            helmDeg = _ovrHelmDeg;
        }
        float sailTarget = sailSign * side * sheetDeg;
        float rudderTarget = rudderSign * helmDeg;
        // Under a fresh local override the hand is already rate-limited by
        // ManualHelm; keeping the full visual slew on top double-limits and the
        // boom drags behind the stick. Doubled, not removed: the tack sweep
        // (side flip) should still look like a boom crossing, not a teleport.
        float slew = (_ovrAt >= 0f && Time.time - _ovrAt < 0.3f) ? sailSlew * 2f : sailSlew;
        _sailAngle = Mathf.MoveTowardsAngle(_sailAngle, sailTarget, slew * Time.deltaTime);
        _rudderAngle = Mathf.MoveTowardsAngle(_rudderAngle, rudderTarget, rudderSlew * Time.deltaTime);

        var sailRot = Quaternion.AngleAxis(_sailAngle, Vector3.up);
        if (_boom) _boom.localRotation = sailRot * _boomRest;
        if (_mainsail) _mainsail.localRotation = sailRot * _sailRest;
        if (_rudder) _rudder.localRotation = Quaternion.AngleAxis(_rudderAngle, Vector3.up) * _rudderRest;

        _tackLuffAge += Time.deltaTime;
        float tackLuff = tackLuffTime > 0f
            ? 1f - Mathf.Clamp01(_tackLuffAge / tackLuffTime)
            : 0f;
        Vector2 response = SailVisualMath.Response(
            apparent.magnitude, windAngle, sheetDeg);
        float fill = response.x * (1f - tackLuff);
        float luff = Mathf.Max(response.y, tackLuff);
        _flutterPhase += Time.deltaTime * flutterHz * Mathf.PI * 2f;
        ApplySailShapes(_mainsailRenderer, _mainsailShapes, fill,
            SailVisualMath.RippleWeights(luff, _flutterPhase), side);
        ApplySailShapes(_jibRenderer, _jibShapes, fill,
            SailVisualMath.RippleWeights(
                Mathf.Clamp01(luff * 1.15f), _flutterPhase * 1.23f + 0.4f), side);
    }

    void ResolveSailShapes(Transform sail, string sailName,
        out SkinnedMeshRenderer renderer, out int[] shapes)
    {
        renderer = sail ? sail.GetComponentInChildren<SkinnedMeshRenderer>() : null;
        shapes = null;
        if (!sail) return;
        if (!renderer || renderer.sharedMesh == null)
        {
            Debug.LogWarning($"ActuatorAnimator: '{sailName}' blend shapes unavailable");
            return;
        }
        shapes = new int[SailShapeNames.Length];
        for (int i = 0; i < shapes.Length; ++i)
        {
            shapes[i] = renderer.sharedMesh.GetBlendShapeIndex(SailShapeNames[i]);
            if (shapes[i] < 0)
            {
                Debug.LogWarning($"ActuatorAnimator: '{sailName}' missing blend shape '{SailShapeNames[i]}'");
                shapes = null;
                return;
            }
        }
    }

    static void ApplySailShapes(SkinnedMeshRenderer renderer, int[] shapes,
        float fill, Vector2 ripple, float side)
    {
        if (renderer == null || shapes == null) return;
        renderer.SetBlendShapeWeight(shapes[0], side < 0f ? fill * 100f : 0f);
        renderer.SetBlendShapeWeight(shapes[1], side > 0f ? fill * 100f : 0f);
        renderer.SetBlendShapeWeight(shapes[2], ripple.x * 100f);
        renderer.SetBlendShapeWeight(shapes[3], ripple.y * 100f);
    }

    Transform FindPart(string name)
    {
        var hit = FindRec(transform, name);
        if (hit == null)
            Debug.LogWarning($"ActuatorAnimator: '{name}' not found under {transform.name}");
        return hit;
    }

    static Transform FindRec(Transform root, string name)
    {
        if (root.name == name) return root;
        foreach (Transform child in root)
        {
            var hit = FindRec(child, name);
            if (hit) return hit;
        }
        return null;
    }
}
