// Copyright (c) 2026 Cyril Moron — EPL-2.0
// Pure motion arithmetic shared by the Unity water-wake implementations.
using UnityEngine;

public static class WakeMath
{
    public static float SpeedFactor(float speed, float refSpeed)
    {
        if (refSpeed <= 0f) return 0f;
        return Mathf.Clamp01(speed / refSpeed);
    }

    public static float WakeStrength(float speed, float refSpeed)
    {
        float factor = SpeedFactor(speed, refSpeed);
        return factor * factor;
    }

    public static float WakeLength(
        float speed, float refSpeed, float minLength, float maxLength)
    {
        if (minLength < 0f || maxLength < minLength) return 0f;
        return Mathf.Lerp(
            minLength, maxLength, SpeedFactor(speed, refSpeed));
    }

    public static float WakePeriod(
        float speed, float minPeriod, float maxPeriod)
    {
        if (speed <= 0f || minPeriod <= 0f || maxPeriod < minPeriod)
            return 0f;
        return Mathf.Clamp(
            2f * Mathf.PI * speed / 9.81f, minPeriod, maxPeriod);
    }

    public static float MotionSpeed(
        float distance, float deltaTime, float maxStep)
    {
        if (distance <= 0f || deltaTime <= 0f ||
            maxStep <= 0f || distance > maxStep)
            return 0f;
        return distance / deltaTime;
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
