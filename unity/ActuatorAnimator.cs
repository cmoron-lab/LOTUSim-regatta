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

    static readonly Regex SheetRe = new Regex(@"""mainsail\(sheet\)""\s*:\s*(-?[\d.eE+-]+)");
    static readonly Regex HelmRe = new Regex(@"""rudder\(helm\)""\s*:\s*(-?[\d.eE+-]+)");

    Transform _boom, _mainsail, _rudder, _hull, _bow;
    float _sheetDeg, _helmDeg;       // latest commanded magnitudes (deg)
    float _sailAngle, _rudderAngle;  // currently displayed local Y angles (deg)
    Quaternion _boomRest, _sailRest, _rudderRest;

    void Start()
    {
        _boom = FindPart("Boom");
        _mainsail = FindPart("Mainsail");
        _rudder = FindPart("Rudder");
        _hull = FindPart("Hull");
        _bow = FindPart("BowNose");
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

    void Update()
    {
        // Bearing of the bow vs wind (from world +Z): >0 = bow east of north =
        // wind on the port side = boom to starboard (positive local yaw).
        float side = 1f;
        if (_hull && _bow)
        {
            Vector3 fwd = _bow.position - _hull.position;
            fwd.y = 0f;
            if (fwd.sqrMagnitude > 1e-6f)
                side = Mathf.Sign(Vector3.SignedAngle(Vector3.forward, fwd, Vector3.up));
        }

        float sailTarget = sailSign * side * _sheetDeg;
        float rudderTarget = rudderSign * _helmDeg;
        _sailAngle = Mathf.MoveTowardsAngle(_sailAngle, sailTarget, sailSlew * Time.deltaTime);
        _rudderAngle = Mathf.MoveTowardsAngle(_rudderAngle, rudderTarget, rudderSlew * Time.deltaTime);

        var sailRot = Quaternion.AngleAxis(_sailAngle, Vector3.up);
        if (_boom) _boom.localRotation = sailRot * _boomRest;
        if (_mainsail) _mainsail.localRotation = sailRot * _sailRest;
        if (_rudder) _rudder.localRotation = Quaternion.AngleAxis(_rudderAngle, Vector3.up) * _rudderRest;
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
