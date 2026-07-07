// Copyright (c) 2026 Cyril Moron — EPL-2.0
// Self-contained camera rig for the regatta. Modes (key C):
//   CHASE   follow behind the boat; RMB-drag = look around it; wheel = distance
//   ORBIT   free orbit centered on the boat; drag = orbit; wheel = zoom
//   ONBOARD helm station; RMB-drag = look around from the cockpit
//   FREE    spectator fly-cam: WASD/QE + RMB-drag look; wheel = speed
// Attach to a Camera. The boat is the object carrying ActuatorAnimator —
// name-independent. "Forward" = smoothed motion direction (convention-free).
using UnityEngine;

public class RegattaCameraRig : MonoBehaviour
{
    public string targetName = "focus_v2";           // fallback if no animator found
    public float chaseDistance = 2.2f, chaseHeight = 1.0f;
    public float orbitDistance = 3f;
    public Vector3 helmOffset = new Vector3(0f, 0.22f, -0.42f); // up, back from motion
    public float freeSpeed = 3f;

    enum Mode { Chase, Orbit, Onboard, Free }
    Mode _mode = Mode.Chase;
    Transform _target;
    Vector3 _dir = Vector3.forward;
    Vector3 _lastPos, _vel;
    float _orbitYaw = 45f, _orbitPitch = 25f;
    float _lookYaw, _lookPitch;                      // drag offset for Chase/Onboard
    float _freeYaw, _freePitch;

    void LateUpdate()
    {
        if (_target == null)
        {
            var anim = FindObjectOfType<ActuatorAnimator>();
            var go = anim != null ? anim.gameObject
                     : GameObject.Find(targetName) ?? GameObject.Find(targetName + "(Clone)");
            if (go == null) return;
            _target = go.transform;
            _lastPos = _target.position;
        }

        if (Input.GetKeyDown(KeyCode.C))
        {
            _mode = (Mode)(((int)_mode + 1) % 4);
            _lookYaw = _lookPitch = 0f;
            if (_mode == Mode.Free)
            {
                Vector3 e = transform.rotation.eulerAngles;
                _freeYaw = e.y; _freePitch = e.x > 180f ? e.x - 360f : e.x;
            }
            // FPS-style cursor capture in Free mode only.
            Cursor.lockState = _mode == Mode.Free ? CursorLockMode.Locked : CursorLockMode.None;
            Cursor.visible = _mode != Mode.Free;
        }

        Vector3 delta = _target.position - _lastPos;
        _lastPos = _target.position;
        delta.y = 0f;
        if (delta.sqrMagnitude > 1e-10f)
            _dir = Vector3.Slerp(_dir, delta.normalized, 0.05f);

        float scroll = Input.GetAxis("Mouse ScrollWheel");
        bool drag = Input.GetMouseButton(1);
        float mx = drag ? Input.GetAxis("Mouse X") * 3f : 0f;
        float my = drag ? Input.GetAxis("Mouse Y") * 3f : 0f;

        switch (_mode)
        {
            case Mode.Chase:
            {
                _lookYaw += mx;
                _lookPitch = Mathf.Clamp(_lookPitch - my, -30f, 60f);
                chaseDistance = Mathf.Clamp(chaseDistance - scroll * 2f, 0.8f, 15f);
                Vector3 back = Quaternion.Euler(_lookPitch, _lookYaw, 0f) * _dir;
                Vector3 pos = _target.position - back * chaseDistance
                              + Vector3.up * chaseHeight;
                transform.position = Vector3.SmoothDamp(transform.position, pos, ref _vel, 0.35f);
                transform.rotation = Quaternion.Slerp(transform.rotation,
                    Quaternion.LookRotation(
                        (_target.position + Vector3.up * 0.3f) - transform.position), 0.1f);
                break;
            }
            case Mode.Orbit:
            {
                orbitDistance = Mathf.Clamp(orbitDistance - scroll * 2f, 0.8f, 20f);
                if (drag || Input.GetMouseButton(0))
                {
                    _orbitYaw += Input.GetAxis("Mouse X") * 3f;
                    _orbitPitch = Mathf.Clamp(_orbitPitch - Input.GetAxis("Mouse Y") * 3f, 5f, 85f);
                }
                Quaternion q = Quaternion.Euler(_orbitPitch, _orbitYaw, 0f);
                transform.position = _target.position + q * (Vector3.back * orbitDistance);
                transform.LookAt(_target.position + Vector3.up * 0.3f);
                break;
            }
            case Mode.Onboard:
            {
                _lookYaw = Mathf.Clamp(_lookYaw + mx, -170f, 170f);
                _lookPitch = Mathf.Clamp(_lookPitch - my, -40f, 60f);
                transform.position = _target.position
                                     + Vector3.up * helmOffset.y + _dir * helmOffset.z;
                float baseYaw = Quaternion.LookRotation(_dir).eulerAngles.y;
                transform.rotation = Quaternion.Slerp(transform.rotation,
                    Quaternion.Euler(_lookPitch, baseYaw + _lookYaw, 0f), 0.2f);
                break;
            }
            case Mode.Free:
            {
                // FPS look: cursor locked, mouse steers directly (no button held).
                // Esc releases the cursor (Unity editor grabs it); click recaptures.
                if (Cursor.lockState != CursorLockMode.Locked && Input.GetMouseButtonDown(0))
                { Cursor.lockState = CursorLockMode.Locked; Cursor.visible = false; }
                bool captured = Cursor.lockState == CursorLockMode.Locked;
                float fx = captured ? Input.GetAxis("Mouse X") * 3f : mx;
                float fy = captured ? Input.GetAxis("Mouse Y") * 3f : my;
                freeSpeed = Mathf.Clamp(freeSpeed * (1f + scroll), 0.3f, 50f);
                _freeYaw += fx;
                _freePitch = Mathf.Clamp(_freePitch - fy, -89f, 89f);
                transform.rotation = Quaternion.Euler(_freePitch, _freeYaw, 0f);
                Vector3 move = new Vector3(Input.GetAxis("Horizontal"), 0f, Input.GetAxis("Vertical"));
                if (Input.GetKey(KeyCode.E)) move.y += 1f;
                if (Input.GetKey(KeyCode.Q)) move.y -= 1f;
                float boost = Input.GetKey(KeyCode.LeftShift) ? 3f : 1f;
                transform.position += transform.rotation * move * freeSpeed * boost * Time.deltaTime;
                break;
            }
        }
    }

    void OnGUI()
    {
        GUI.Label(new Rect(10, 10, 560, 24),
            $"[C] camera: {_mode} | v3 | " +
            (_target == null ? "waiting for boat..." : $"target: {_target.name}") +
            "  (RMB-drag: look, wheel: zoom/speed)");
    }
}
