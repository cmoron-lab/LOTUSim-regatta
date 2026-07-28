// Copyright (c) 2026 Cyril Moron — EPL-2.0
// World-space foam stamps projected directly onto HDRP water.
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

public class WakeEmitter : MonoBehaviour
{
    public float refSpeed = 0.5f;
    public float minSpeed = 0.03f;
    public float maxStep = 0.25f;
    public float emissionSpacing = 0.12f;
    public float stampWidth = 0.18f;
    public float stampLength = 0.30f;
    public float lifetime = 5f;
    public float wakeAngle = 19.5f;
    public float projectorDepth = 1f;
    public float smoothing = 0.15f;

    const int PairCapacity = 48;
    const string MaterialResource = "RegattaWakeDecal";
    const string FoamTextureProperty = "_BaseColorMap";
    const int FoamTextureWidth = 64;
    const int FoamTextureHeight = 128;

    sealed class Stamp
    {
        public DecalProjector projector;
        public Vector3 origin;
        public Vector3 right;
        public float speed;
        public float age;
        public int side;
        public bool active;
    }

    Transform _rudder;
    WaterSurface _water;
    GameObject _wakeRoot;
    Material _mat;
    Texture2D _foam;
    Stamp[] _stamps;
    Vector3 _lastPos;
    float _speed;
    float _distanceSinceEmission;
    int _nextPair;

    void Start()
    {
        if (refSpeed <= 0f || minSpeed < 0f || maxStep <= 0f ||
            emissionSpacing <= 0f || stampWidth <= 0f ||
            stampLength <= 0f || lifetime <= 0f ||
            wakeAngle < 0f || wakeAngle >= 90f ||
            projectorDepth <= 0f)
        {
            Debug.LogError("WakeEmitter: invalid calibration — disabling.");
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
        if (_water == null)
        {
            Debug.LogError("WakeEmitter: WaterSurface not found — disabling.");
            enabled = false;
            return;
        }

        Material source = Resources.Load<Material>(MaterialResource);
        if (source == null)
        {
            Debug.LogError(
                $"WakeEmitter: material resource '{MaterialResource}' " +
                "not found — disabling.");
            enabled = false;
            return;
        }

        _mat = new Material(source) { name = "Regatta Wake (runtime)" };
        _foam = BuildFoamTexture(FoamTextureWidth, FoamTextureHeight);
        _mat.SetTexture(FoamTextureProperty, _foam);
        if (!HDMaterial.ValidateMaterial(_mat))
        {
            Debug.LogError(
                "WakeEmitter: invalid HDRP decal material — disabling.");
            enabled = false;
            return;
        }

        MakePool();
        _lastPos = transform.position;
    }

    void Update()
    {
        UpdateStamps();

        Vector3 delta = transform.position - _lastPos;
        _lastPos = transform.position;
        delta.y = 0f;
        float distance = delta.magnitude;

        if (distance > maxStep)
        {
            _speed = 0f;
            _distanceSinceEmission = 0f;
            ClearStamps();
            return;
        }

        float instant = Time.deltaTime > 0f ? distance / Time.deltaTime : 0f;
        float blend = smoothing > 0f
            ? Mathf.Clamp01(Time.deltaTime / smoothing)
            : 1f;
        _speed = Mathf.Lerp(_speed, instant, blend);
        _distanceSinceEmission += distance;

        if (distance > 0f && WakeMath.ShouldEmit(
                _distanceSinceEmission, emissionSpacing, _speed, minSpeed))
        {
            EmitPair(delta / distance);
            _distanceSinceEmission = 0f;
        }
    }

    void MakePool()
    {
        _wakeRoot = new GameObject("WakeDecals");
        _stamps = new Stamp[PairCapacity * 2];
        for (int i = 0; i < _stamps.Length; i++)
        {
            var go = new GameObject($"WakeStamp-{i:00}");
            go.transform.SetParent(_wakeRoot.transform, false);
            var projector = go.AddComponent<DecalProjector>();
            projector.material = _mat;
            projector.size =
                new Vector3(stampWidth, stampLength, projectorDepth);
            projector.drawDistance = 100f;
            projector.fadeFactor = 0f;
            projector.enabled = false;
            _stamps[i] = new Stamp { projector = projector };
        }
    }

    void EmitPair(Vector3 forward)
    {
        Vector3 right = Vector3.Cross(Vector3.up, forward).normalized;
        Vector3 origin = new Vector3(
            _rudder.position.x,
            _water.transform.position.y,
            _rudder.position.z);
        float tangent = Mathf.Tan(wakeAngle * Mathf.Deg2Rad);

        for (int i = 0; i < 2; i++)
        {
            int side = i == 0 ? -1 : 1;
            Stamp stamp = _stamps[_nextPair * 2 + i];
            Vector3 arm = (forward - side * right * tangent).normalized;

            stamp.origin = origin;
            stamp.right = right;
            stamp.speed = _speed;
            stamp.age = 0f;
            stamp.side = side;
            stamp.active = true;
            stamp.projector.transform.SetPositionAndRotation(
                origin, Quaternion.LookRotation(Vector3.down, arm));
            stamp.projector.fadeFactor =
                WakeMath.SpeedFactor(_speed, refSpeed);
            stamp.projector.enabled = true;
        }

        _nextPair = WakeMath.NextPairIndex(_nextPair, PairCapacity);
    }

    void UpdateStamps()
    {
        if (_stamps == null) return;

        foreach (Stamp stamp in _stamps)
        {
            if (!stamp.active) continue;

            stamp.age += Time.deltaTime;
            float fade = WakeMath.Fade(stamp.age, lifetime);
            if (fade <= 0f)
            {
                stamp.active = false;
                stamp.projector.enabled = false;
                continue;
            }

            stamp.projector.transform.position = WakeMath.StampPosition(
                stamp.origin, stamp.right, stamp.side, stamp.age,
                stamp.speed, wakeAngle);
            stamp.projector.fadeFactor =
                fade * WakeMath.SpeedFactor(stamp.speed, refSpeed);
        }
    }

    void ClearStamps()
    {
        if (_stamps == null) return;

        foreach (Stamp stamp in _stamps)
        {
            stamp.active = false;
            stamp.projector.enabled = false;
        }
        _nextPair = 0;
    }

    static Texture2D BuildFoamTexture(int width, int height)
    {
        var tex = new Texture2D(
            width, height, TextureFormat.RGBA32, mipChain: true);
        for (int py = 0; py < height; py++)
            for (int px = 0; px < width; px++)
            {
                float u = (px + 0.5f) / width;
                float v = (py + 0.5f) / height;
                float x = 2f * u - 1f;
                float y = 2f * v - 1f;
                float ellipse = Mathf.Clamp01(1f - x * x - y * y);
                float breakup = Mathf.Clamp01(
                    0.72f +
                    0.18f * Mathf.Sin(2f * Mathf.PI * (2f * v + u)) +
                    0.10f * Mathf.Sin(2f * Mathf.PI * (5f * v - 3f * u)));
                float alpha = ellipse * ellipse * breakup;
                tex.SetPixel(px, py, new Color(1f, 1f, 1f, alpha));
            }
        tex.Apply(updateMipmaps: true, makeNoLongerReadable: false);
        tex.wrapMode = TextureWrapMode.Clamp;
        tex.filterMode = FilterMode.Bilinear;
        return tex;
    }

    void OnDestroy()
    {
        if (_wakeRoot != null) Destroy(_wakeRoot);
        if (_mat != null) Destroy(_mat);
        if (_foam != null) Destroy(_foam);
    }

    Transform FindPart(string name)
    {
        foreach (Transform child in GetComponentsInChildren<Transform>(true))
            if (child.name == name) return child;
        return null;
    }
}
