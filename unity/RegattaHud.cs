// Copyright (c) 2026 Cyril Moron — EPL-2.0
// Bottom-screen sailing HUD: heading, speed, true wind angle -- the three
// numbers a helmsman needs while learning to beat upwind, which is the whole
// point of the exercise. TWA goes red inside the no-go zone: the visible
// lesson that you cannot point at the mark.
//
// Wind is the scenario's constant, FROM world +Z (north) -- the same
// assumption ActuatorAnimator renders the boom with. Attach to the camera
// next to RegattaCameraRig. Pure IMGUI, no assets, no canvas.
using UnityEngine;

public class RegattaHud : MonoBehaviour
{
    public float noGoDeg = 45f;   // under this TWA the boat cannot make way

    ActuatorAnimator _anim;
    Transform _boat;
    Vector3 _lastPos;
    float _speed;                 // m/s, EMA-smoothed
    float _heading, _twaSigned;   // deg; TWA sign = which side the wind is on
    GUIStyle _panel, _tag, _num, _sub;
    Texture2D _bg;

    void LateUpdate()
    {
        if (_boat == null)
        {
            _anim = FindObjectOfType<ActuatorAnimator>();
            if (_anim == null) return;
            _boat = _anim.transform;
            _lastPos = _boat.position;
            return;
        }
        Vector3 d = _boat.position - _lastPos;
        _lastPos = _boat.position;
        d.y = 0f;
        if (Time.deltaTime > 0f)
            _speed = Mathf.Lerp(_speed, d.magnitude / Time.deltaTime, 0.05f);

        Vector3 bow = _anim.BowAxis;
        if (bow != Vector3.zero)
        {
            float h = Vector3.SignedAngle(Vector3.forward, bow, Vector3.up);
            _heading = (h + 360f) % 360f;
            _twaSigned = Mathf.DeltaAngle(0f, h);  // wind FROM north: TWA = heading off it
        }
    }

    void OnGUI()
    {
        if (_boat == null) return;
        if (_bg == null) BuildStyles();

        const float W = 620f, H = 92f;
        var panel = new Rect((Screen.width - W) / 2f, Screen.height - H - 16f, W, H);
        GUI.Box(panel, GUIContent.none, _panel);

        float cw = W / 3f;
        float twa = Mathf.Abs(_twaSigned);
        bool noGo = twa < noGoDeg;
        // Cyan for live numbers, red for the zone the boat cannot sail. The side
        // tag doubles as tack awareness: wind over PORT or STBD.
        var cyan = new Color(0.35f, 0.95f, 1f);
        var red = new Color(1f, 0.30f, 0.25f);

        Cell(new Rect(panel.x, panel.y, cw, H), "HDG",
            $"{_heading:000}°", Cardinal(_heading), cyan);
        Cell(new Rect(panel.x + cw, panel.y, cw, H), "SPEED",
            $"{_speed:0.00}", "m/s", cyan);
        Cell(new Rect(panel.x + 2 * cw, panel.y, cw, H), "TWA",
            $"{twa:0}°",
            noGo ? "NO-GO ZONE" : (_twaSigned < 0f ? "wind over PORT" : "wind over STBD"),
            noGo ? red : cyan);
    }

    void Cell(Rect r, string tag, string value, string sub, Color c)
    {
        GUI.Label(new Rect(r.x, r.y + 8f, r.width, 16f), tag, _tag);
        // Cheap drop shadow: same text, offset, black -- IMGUI has no better.
        _num.normal.textColor = Color.black;
        GUI.Label(new Rect(r.x + 2f, r.y + 26f, r.width, 40f), value, _num);
        _num.normal.textColor = c;
        GUI.Label(new Rect(r.x, r.y + 24f, r.width, 40f), value, _num);
        GUI.Label(new Rect(r.x, r.y + 64f, r.width, 18f), sub, _sub);
    }

    static string Cardinal(float deg)
    {
        string[] pts = { "N", "NE", "E", "SE", "S", "SW", "W", "NW" };
        return pts[Mathf.RoundToInt(deg / 45f) % 8];
    }

    void BuildStyles()
    {
        _bg = new Texture2D(1, 1);
        _bg.SetPixel(0, 0, new Color(0.02f, 0.05f, 0.09f, 0.62f));
        _bg.Apply();
        _panel = new GUIStyle { normal = { background = _bg } };
        _tag = new GUIStyle
        {
            alignment = TextAnchor.MiddleCenter, fontSize = 12,
            normal = { textColor = new Color(1f, 1f, 1f, 0.55f) },
        };
        _num = new GUIStyle
        {
            alignment = TextAnchor.MiddleCenter, fontSize = 34,
            fontStyle = FontStyle.Bold, normal = { textColor = Color.white },
        };
        _sub = new GUIStyle
        {
            alignment = TextAnchor.MiddleCenter, fontSize = 13,
            normal = { textColor = new Color(1f, 1f, 1f, 0.75f) },
        };
    }
}
