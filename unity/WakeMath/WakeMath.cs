// Copyright (c) 2026 Cyril Moron — EPL-2.0
// Pure motion arithmetic for the Unity water-decal wake.
using UnityEngine;

public static class WakeMath
{
    public static float SpeedFactor(float speed, float refSpeed)
    {
        if (refSpeed <= 0f) return 0f;
        return Mathf.Clamp01(speed / refSpeed);
    }

    public static bool ShouldEmit(
        float distance, float spacing, float speed, float minSpeed)
    {
        return spacing > 0f && distance >= spacing && speed >= minSpeed;
    }

    public static float LateralOffset(
        float age, float speed, float angleDegrees)
    {
        if (age <= 0f || speed <= 0f ||
            angleDegrees < 0f || angleDegrees >= 90f)
            return 0f;
        return age * speed * Mathf.Tan(angleDegrees * Mathf.Deg2Rad);
    }

    public static Vector3 StampPosition(
        Vector3 origin, Vector3 right, int side, float age,
        float speed, float angleDegrees)
    {
        return origin + Mathf.Sign(side) * right.normalized *
            LateralOffset(age, speed, angleDegrees);
    }

    public static float Fade(float age, float lifetime)
    {
        if (lifetime <= 0f) return 0f;
        return 1f - Mathf.Clamp01(age / lifetime);
    }

    public static int NextPairIndex(int current, int capacity)
    {
        if (capacity <= 0) return 0;
        return (current + 1) % capacity;
    }
}
