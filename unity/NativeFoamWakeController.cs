// Copyright (c) 2026 Cyril Moron — EPL-2.0
using UnityEngine;
using UnityEngine.Rendering.HighDefinition;

public class NativeFoamWakeController : MonoBehaviour
{
    // ponytail: four foam generators per boat fit the current single-boat
    // scenario; use a shared pool before exceeding HDRP's global limit of 64.
    public float refSpeed = 0.8f;
    public float minSpeed = 0.04f;
    public float maxStep = 0.25f;
    public float minWakePeriod = 0.35f;
    public float maxWakePeriod = 0.8f;
    public float minWakeLength = 0.25f;
    public float maxWakeLength = 1.3f;
    public float wakeAngle = 19.5f;
    public Vector2 wakeBrushSize = new Vector2(0.12f, 0.18f);
    public float maxDimmer = 0.75f;
    public float smoothing = 0.15f;
    public Vector2 sternFoamSize = new Vector2(0.16f, 0.34f);
    public float sternFoamDimmer = 0.22f;
    public Vector2 bowFoamSize = new Vector2(0.28f, 0.5f);
    public float bowFoamDimmer = 0.25f;
    public Vector2 bowWaveSize = new Vector2(1f, 2f);
    public float bowWaveDepth = 0.12f;
    public float bowWaveElevation = 0.1f;

    Transform _boat;
    Transform _bow;
    ActuatorAnimator _animator;
    WaterSurface _water;
    WaterFoamGenerator _portFoam;
    WaterFoamGenerator _starboardFoam;
    GameObject _sternFoamObject;
    WaterFoamGenerator _sternFoam;
    GameObject _bowFoamObject;
    WaterFoamGenerator _bowFoam;
    GameObject _bowWaveObject;
    WaterDeformer _bowWave;
    Vector3 _lastPosition;
    Vector3 _forward;
    Vector3 _crestOrigin;
    Vector3 _crestForward;
    Vector3 _crestRight;
    float _speed;
    float _crestAge;
    float _crestPeriod;
    float _crestLength;
    float _crestStrength;
    bool _crestActive;

    void Start()
    {
        if (refSpeed <= 0f || minSpeed < 0f || maxStep <= 0f ||
            minWakePeriod <= 0f || maxWakePeriod < minWakePeriod ||
            minWakeLength < 0f || maxWakeLength < minWakeLength ||
            wakeAngle < 0f || wakeAngle >= 90f ||
            wakeBrushSize.x <= 0f || wakeBrushSize.y <= 0f ||
            maxDimmer < 0f || maxDimmer > 1f || smoothing < 0f ||
            sternFoamSize.x <= 0f || sternFoamSize.y <= 0f ||
            sternFoamDimmer < 0f || sternFoamDimmer > 1f ||
            bowFoamSize.x <= 0f || bowFoamSize.y <= 0f ||
            bowFoamDimmer < 0f || bowFoamDimmer > 1f ||
            bowWaveSize.x <= 0f || bowWaveSize.y <= 0f ||
            bowWaveDepth < 0f || bowWaveElevation < 0f)
        {
            Debug.LogError(
                "NativeFoamWakeController: invalid calibration — disabling.");
            enabled = false;
            return;
        }

        _boat = transform.parent ? transform.parent : transform;
        _bow = FindPart(_boat, "BowNose");
        _animator = _boat.GetComponent<ActuatorAnimator>();
        _water = FindFirstObjectByType<WaterSurface>();
        WaterFoamGenerator[] generators =
            GetComponentsInChildren<WaterFoamGenerator>(true);
        if (_bow == null || _water == null || generators.Length < 2)
        {
            Debug.LogError(
                "NativeFoamWakeController: BowNose, WaterSurface or foam " +
                "generators missing — disabling.");
            enabled = false;
            return;
        }

        _portFoam = generators[0];
        _starboardFoam = generators[1];
        ConfigureWakeBrush(_portFoam);
        ConfigureWakeBrush(_starboardFoam);
        MakeSternFoam();
        MakeBowFoam();
        MakeBowWave();

        _lastPosition = _boat.position;
        _forward = CurrentForward(_boat.right);
        UpdateBowEffects(_forward, 0f);
    }

    void Update()
    {
        Vector3 delta = _boat.position - _lastPosition;
        _lastPosition = _boat.position;
        delta.y = 0f;

        float distance = delta.magnitude;
        float instant = WakeMath.MotionSpeed(
            distance, Time.deltaTime, maxStep);
        if (distance > maxStep)
        {
            _speed = 0f;
            StopCrest();
            distance = 0f;
        }
        else
        {
            float blend = smoothing > 0f
                ? Mathf.Clamp01(Time.deltaTime / smoothing)
                : 1f;
            _speed = Mathf.Lerp(_speed, instant, blend);
        }

        _forward = CurrentForward(
            distance > 0f ? delta / distance : _forward);
        float strength = _speed >= minSpeed
            ? WakeMath.WakeStrength(_speed, refSpeed)
            : 0f;

        if (strength > 0f)
        {
            if (!_crestActive || _crestAge >= _crestPeriod)
                BeginCrest(strength);
            UpdateCrest();
            _crestAge += Time.deltaTime;
        }
        else
            StopCrest();

        UpdateBowEffects(_forward, strength);
        UpdateSternFoam(_forward, strength);
    }

    void ConfigureWakeBrush(WaterFoamGenerator generator)
    {
        generator.type = WaterFoamGeneratorType.Disk;
        generator.texture = null;
        generator.regionSize = wakeBrushSize;
        generator.surfaceFoamDimmer = 0f;
        generator.deepFoamDimmer = 0f;
        generator.enabled = true;
    }

    void BeginCrest(float strength)
    {
        _crestOrigin = transform.position;
        _crestOrigin.y = _water.transform.position.y;
        _crestForward = _forward;
        _crestRight =
            Vector3.Cross(Vector3.up, _crestForward).normalized;
        _crestPeriod = WakeMath.WakePeriod(
            _speed, minWakePeriod, maxWakePeriod);
        _crestLength = WakeMath.WakeLength(
            _speed, refSpeed, minWakeLength, maxWakeLength);
        _crestStrength = strength;
        _crestAge = 0f;
        _crestActive = _crestPeriod > 0f;
    }

    void UpdateCrest()
    {
        float progress = Mathf.Clamp01(_crestAge / _crestPeriod);
        float distance = _crestLength * progress;
        Vector3 center = _crestOrigin - _crestForward * distance;
        Vector3 side =
            _crestRight * distance *
            Mathf.Tan(wakeAngle * Mathf.Deg2Rad);
        Quaternion rotation =
            Quaternion.LookRotation(_crestForward, Vector3.up);

        _portFoam.transform.SetPositionAndRotation(
            center - side, rotation);
        _starboardFoam.transform.SetPositionAndRotation(
            center + side, rotation);

        float fade = Mathf.Lerp(
            0.25f, 1f, WakeMath.Fade(_crestAge, _crestPeriod));
        float dimmer = maxDimmer * _crestStrength * fade;
        _portFoam.surfaceFoamDimmer = dimmer;
        _starboardFoam.surfaceFoamDimmer = dimmer;
    }

    void StopCrest()
    {
        _crestActive = false;
        if (_portFoam != null) _portFoam.surfaceFoamDimmer = 0f;
        if (_starboardFoam != null)
            _starboardFoam.surfaceFoamDimmer = 0f;
    }

    void MakeBowFoam()
    {
        _bowFoamObject = new GameObject("NativeBowFoam");
        _bowFoamObject.transform.SetParent(_boat, false);
        _bowFoam = _bowFoamObject.AddComponent<WaterFoamGenerator>();
        _bowFoam.type = WaterFoamGeneratorType.Disk;
        _bowFoam.regionSize = bowFoamSize;
        _bowFoam.surfaceFoamDimmer = 0f;
        _bowFoam.deepFoamDimmer = 0f;
    }

    void MakeSternFoam()
    {
        _sternFoamObject = new GameObject("NativeSternFoam");
        _sternFoamObject.transform.SetParent(_boat, false);
        _sternFoam = _sternFoamObject.AddComponent<WaterFoamGenerator>();
        _sternFoam.type = WaterFoamGeneratorType.Disk;
        _sternFoam.regionSize = sternFoamSize;
        _sternFoam.surfaceFoamDimmer = 0f;
        _sternFoam.deepFoamDimmer = 0f;
    }

    void MakeBowWave()
    {
        _bowWaveObject = new GameObject("NativeBowWave");
        _bowWaveObject.transform.SetParent(_boat, false);
        _bowWave = _bowWaveObject.AddComponent<WaterDeformer>();
        _bowWave.type = WaterDeformerType.BowWave;
        _bowWave.regionSize = bowWaveSize;
        _bowWave.amplitude = 0f;
        _bowWave.bowWaveElevation = 0f;
        _bowWave.surfaceFoamDimmer = 0f;
        _bowWave.deepFoamDimmer = 0f;
        _bowWave.enabled = false;
    }

    void UpdateBowEffects(Vector3 forward, float strength)
    {
        Vector3 bow = _bow.position;
        bow.y = _water.transform.position.y;
        Quaternion rotation = Quaternion.LookRotation(forward, Vector3.up);
        _bowFoam.transform.SetPositionAndRotation(bow, rotation);
        _bowFoam.surfaceFoamDimmer = bowFoamDimmer * strength;

        if (strength <= 0f)
        {
            _bowWave.enabled = false;
            return;
        }

        _bowWaveObject.transform.SetPositionAndRotation(
            bow - forward * (0.35f * bowWaveSize.y),
            Quaternion.LookRotation(-forward, Vector3.up));
        _bowWave.amplitude = -bowWaveDepth * strength;
        _bowWave.bowWaveElevation = bowWaveElevation * strength;
        _bowWave.enabled = true;
    }

    void UpdateSternFoam(Vector3 forward, float strength)
    {
        Vector3 stern = transform.position;
        stern.y = _water.transform.position.y;
        _sternFoam.transform.SetPositionAndRotation(
            stern, Quaternion.LookRotation(forward, Vector3.up));
        _sternFoam.surfaceFoamDimmer = sternFoamDimmer * strength;
    }

    Vector3 CurrentForward(Vector3 fallback)
    {
        Vector3 forward =
            _animator != null ? _animator.BowAxis : Vector3.zero;
        forward.y = 0f;
        if (forward.sqrMagnitude <= 1e-6f)
        {
            forward = fallback;
            forward.y = 0f;
        }
        return forward.sqrMagnitude > 1e-6f
            ? forward.normalized
            : Vector3.right;
    }

    static Transform FindPart(Transform root, string name)
    {
        if (root.name == name) return root;
        foreach (Transform child in root)
        {
            Transform hit = FindPart(child, name);
            if (hit != null) return hit;
        }
        return null;
    }

    void OnDisable()
    {
        StopCrest();
        if (_sternFoam != null) _sternFoam.surfaceFoamDimmer = 0f;
        if (_bowFoam != null) _bowFoam.surfaceFoamDimmer = 0f;
        if (_bowWave != null) _bowWave.enabled = false;
    }

    void OnDestroy()
    {
        if (_sternFoamObject != null) Destroy(_sternFoamObject);
        if (_bowFoamObject != null) Destroy(_bowFoamObject);
        if (_bowWaveObject != null) Destroy(_bowWaveObject);
    }
}
