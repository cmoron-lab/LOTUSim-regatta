// Copyright (c) 2026 Cyril Moron — EPL-2.0
// Continuous water-bound wake driven by the boat's own horizontal motion.
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

public class WakeEmitter : MonoBehaviour
{
    public float seaLevel = 0f;
    public float surfaceOffset = 0.005f;
    public float refSpeed = 0.5f;
    public float minSpeed = 0.03f;
    public float maxStep = 0.25f;
    public float minVertexDistance = 0.03f;
    public float wakeWidth = 0.30f;
    public float lifetime = 6f;
    public float smoothing = 0.15f;

    const string ShaderResource = "RegattaWake";
    const string FoamTextureProperty = "_MainTex";
    const int FoamTextureWidth = 128;
    const int FoamTextureHeight = 64;

    static readonly Quaternion FlatRotation =
        Quaternion.LookRotation(Vector3.up, Vector3.forward);

    TrailRenderer _trail;
    Transform _rudder;
    Material _mat;
    Texture2D _foam;
    WaterSurface _water;
    Vector3 _lastPos;
    float _speed;

    void Start()
    {
        if (refSpeed <= 0f || minSpeed < 0f || maxStep <= 0f ||
            minVertexDistance <= 0f || wakeWidth <= 0f || lifetime <= 0f)
        {
            Debug.LogError("WakeEmitter: invalid calibration — disabling.");
            enabled = false;
            return;
        }

        var shader = Resources.Load<Shader>(ShaderResource);
        if (shader == null)
        {
            Debug.LogError($"WakeEmitter: shader resource '{ShaderResource}' not found — disabling.");
            enabled = false;
            return;
        }

        _rudder = FindPart("Rudder");
        if (_rudder == null)
        {
            Debug.LogError("WakeEmitter: 'Rudder' not found — disabling.");
            enabled = false;
            return;
        }

        _water = FindObjectOfType<WaterSurface>();
        if (_water != null)
            _water.cpuEvaluateRipples = true;

        _mat = new Material(shader) { name = "Regatta Wake (runtime)" };
        _foam = BuildFoamTexture(FoamTextureWidth, FoamTextureHeight);
        if (!_mat.HasProperty(FoamTextureProperty))
        {
            Debug.LogError($"WakeEmitter: material property '{FoamTextureProperty}' " +
                           "not found — disabling.");
            enabled = false;
            return;
        }
        _mat.SetTexture(FoamTextureProperty, _foam);

        _trail = MakeTrail();
        _lastPos = transform.position;
        PlaceTrail();
        _trail.Clear();
    }

    void Update()
    {
        Vector3 delta = transform.position - _lastPos;
        _lastPos = transform.position;
        delta.y = 0f;
        PlaceTrail();

        if (delta.magnitude > maxStep)
        {
            _speed = 0f;
            _trail.emitting = false;
            _trail.Clear();
            return;
        }

        float instant = Time.deltaTime > 0f
            ? delta.magnitude / Time.deltaTime
            : 0f;
        float blend = smoothing > 0f
            ? Mathf.Clamp01(Time.deltaTime / smoothing)
            : 1f;
        _speed = Mathf.Lerp(_speed, instant, blend);

        _trail.widthMultiplier = WakeMath.WakeWidth(_speed, refSpeed, wakeWidth);
        _trail.emitting = _speed >= minSpeed && _trail.widthMultiplier > 0f;
    }

    TrailRenderer MakeTrail()
    {
        var go = new GameObject("WakeTrail");
        go.transform.SetParent(transform, worldPositionStays: false);
        var trail = go.AddComponent<TrailRenderer>();
        trail.material = _mat;
        trail.alignment = LineAlignment.TransformZ;
        trail.textureMode = LineTextureMode.Stretch;
        trail.generateLightingData = true;
        trail.receiveShadows = false;
        trail.time = lifetime;
        trail.minVertexDistance = minVertexDistance;
        trail.widthMultiplier = 0f;
        trail.widthCurve = new AnimationCurve(
            new Keyframe(0f, 1f),
            new Keyframe(0.75f, 0.65f),
            new Keyframe(1f, 0.2f));
        trail.numCornerVertices = 2;
        trail.numCapVertices = 2;
        trail.emitting = false;

        var gradient = new Gradient();
        gradient.SetKeys(
            new[] {
                new GradientColorKey(Color.white, 0f),
                new GradientColorKey(Color.white, 1f)
            },
            new[] {
                new GradientAlphaKey(0.85f, 0f),
                new GradientAlphaKey(0.45f, 0.55f),
                new GradientAlphaKey(0f, 1f)
            });
        trail.colorGradient = gradient;
        return trail;
    }

    void PlaceTrail()
    {
        Vector3 p = _rudder.position;
        bool sampled = false;
        float waterHeight = 0f;
        if (_water != null)
        {
            var search = new WaterSearchParameters {
                targetPosition = p,
                startPosition = p,
                error = 0.01f,
                maxIterations = 8
            };
            sampled = _water.FindWaterSurfaceHeight(search, out var result);
            waterHeight = result.height;
        }
        p.y = WakeMath.SurfaceHeight(
            seaLevel, surfaceOffset, sampled, waterHeight);
        _trail.transform.SetPositionAndRotation(p, FlatRotation);
    }

    static Texture2D BuildFoamTexture(int width, int height)
    {
        var tex = new Texture2D(width, height, TextureFormat.RGBA32, mipChain: true);
        for (int y = 0; y < height; y++)
            for (int x = 0; x < width; x++)
            {
                float u = (x + 0.5f) / width;
                float v = (y + 0.5f) / height;
                float shoulders = Mathf.Max(
                    Band(v, 0.27f, 0.30f),
                    Band(v, 0.73f, 0.30f));
                float breakup = Mathf.Clamp01(
                    0.70f +
                    0.18f * Mathf.Sin(2f * Mathf.PI * (1.5f * u + v)) +
                    0.12f * Mathf.Sin(2f * Mathf.PI * (4f * u - 2f * v)));
                float a = Band(v, 0.5f, 0.5f) *
                    (0.25f + 0.65f * shoulders) * breakup;
                a = a * a * (3f - 2f * a);
                tex.SetPixel(x, y, new Color(1f, 1f, 1f, a));
            }
        tex.Apply(updateMipmaps: true, makeNoLongerReadable: false);
        tex.wrapMode = TextureWrapMode.Repeat;
        tex.filterMode = FilterMode.Bilinear;
        return tex;
    }

    static float Band(float value, float centre, float halfWidth)
    {
        return Mathf.Clamp01(1f - Mathf.Abs(value - centre) / halfWidth);
    }

    void OnDestroy()
    {
        if (_mat != null) Destroy(_mat);
        if (_foam != null) Destroy(_foam);
    }

    Transform FindPart(string name)
    {
        foreach (var t in GetComponentsInChildren<Transform>(true))
            if (t.name == name) return t;
        return null;
    }
}
