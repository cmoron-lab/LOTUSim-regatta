// Copyright (c) 2026 Cyril Moron — EPL-2.0
// Self-contained camera rig for the regatta: CHASE / ORBIT / ONBOARD, all
// centered on the spawned boat. Attach to a Camera GameObject; the boat is
// found by name once the bridge spawns it. Independent from the (broken)
// defense-scene camera scripts.
//
// Keys: C cycle mode | mouse drag = orbit (ORBIT mode) | scroll = zoom.
// "Forward" is the smoothed motion direction — convention-free, so no axis
// assumption can bite. ponytail: direction freezes for the few seconds the
// boat is head-to-wind in a tack; acceptable, revisit if it annoys.
using UnityEngine;

public class RegattaCameraRig : MonoBehaviour
{
    public string targetName = "focus_v2(Clone)";
    public float chaseDistance = 2.2f, chaseHeight = 1.0f;
    public float orbitDistance = 3f;
    public Vector3 onboardOffset = new Vector3(0f, 0.35f, -0.30f); // up, back (vs motion)

    enum Mode { Chase, Orbit, Onboard }
    Mode _mode = Mode.Chase;
    Transform _target;
    Vector3 _dir = Vector3.forward;   // smoothed motion direction
    Vector3 _lastPos, _vel;
    float _orbitYaw = 45f, _orbitPitch = 25f;

    void LateUpdate()
    {
        if (_target == null)
        {
            var go = GameObject.Find(targetName);
            if (go == null) return;
            _target = go.transform;
            _lastPos = _target.position;
        }

        if (Input.GetKeyDown(KeyCode.C))
            _mode = (Mode)(((int)_mode + 1) % 3);

        // Smoothed horizontal motion direction (the boat's effective heading).
        Vector3 delta = _target.position - _lastPos;
        _lastPos = _target.position;
        delta.y = 0f;
        if (delta.sqrMagnitude > 1e-10f)
            _dir = Vector3.Slerp(_dir, delta.normalized, 0.05f);

        float scroll = Input.GetAxis("Mouse ScrollWheel");

        switch (_mode)
        {
            case Mode.Chase:
                chaseDistance = Mathf.Clamp(chaseDistance - scroll * 2f, 0.8f, 15f);
                Vector3 chasePos = _target.position - _dir * chaseDistance
                                   + Vector3.up * chaseHeight;
                transform.position = Vector3.SmoothDamp(
                    transform.position, chasePos, ref _vel, 0.4f);
                transform.rotation = Quaternion.Slerp(transform.rotation,
                    Quaternion.LookRotation(
                        (_target.position + Vector3.up * 0.3f) - transform.position),
                    0.1f);
                break;

            case Mode.Orbit:
                orbitDistance = Mathf.Clamp(orbitDistance - scroll * 2f, 0.8f, 20f);
                if (Input.GetMouseButton(0) || Input.GetMouseButton(1))
                {
                    _orbitYaw += Input.GetAxis("Mouse X") * 3f;
                    _orbitPitch = Mathf.Clamp(
                        _orbitPitch - Input.GetAxis("Mouse Y") * 3f, 5f, 85f);
                }
                Quaternion q = Quaternion.Euler(_orbitPitch, _orbitYaw, 0f);
                transform.position = _target.position + q * (Vector3.back * orbitDistance);
                transform.LookAt(_target.position + Vector3.up * 0.3f);
                break;

            case Mode.Onboard:
                transform.position = _target.position
                                     + Vector3.up * onboardOffset.y
                                     + _dir * onboardOffset.z;
                transform.rotation = Quaternion.Slerp(transform.rotation,
                    Quaternion.LookRotation(_dir + Vector3.down * 0.1f), 0.15f);
                break;
        }
    }

    void OnGUI()
    {
        GUI.Label(new Rect(10, 10, 400, 24),
            $"[C] camera: {_mode}" + (_target == null ? "  (waiting for boat...)" : ""));
    }
}
