// Copyright (c) 2026 Cyril Moron — EPL-2.0
// Pure speed-to-width mapping for the Unity wake trail.
using UnityEngine;

public static class WakeMath
{
    public static float SpeedFactor(float speed, float refSpeed)
    {
        if (refSpeed <= 0f) return 0f;
        return Mathf.Clamp01(speed / refSpeed);
    }

    public static float WakeWidth(float speed, float refSpeed, float maxWidth)
    {
        if (maxWidth <= 0f) return 0f;
        return maxWidth * SpeedFactor(speed, refSpeed);
    }

    public static float SurfaceHeight(
        float seaLevel, float offset, bool sampled, float waterHeight)
    {
        return (sampled ? waterHeight : seaLevel) + offset;
    }
}
