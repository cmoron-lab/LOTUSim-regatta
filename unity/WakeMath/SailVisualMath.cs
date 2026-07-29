using UnityEngine;

public static class SailVisualMath
{
    public static Vector3 ApparentWind(
        Vector3 trueAirVelocity, Vector3 boatVelocity)
    {
        trueAirVelocity.y = 0f;
        boatVelocity.y = 0f;
        return trueAirVelocity - boatVelocity;
    }

    public static float OptimalSheet(float windAngle)
    {
        return Mathf.Clamp(0.6f * (Mathf.Abs(windAngle) - 42f), 4f, 80f);
    }

    public static float StableSide(float windAngle, float lastSide)
    {
        float magnitude = Mathf.Abs(windAngle);
        return magnitude <= 5f || magnitude >= 175f
            ? lastSide
            : Mathf.Sign(windAngle);
    }

    // x = filled camber, y = loose luff, both 0..1.
    public static Vector2 Response(
        float apparentSpeed, float windAngle, float sheetDeg)
    {
        if (apparentSpeed <= 0.05f) return Vector2.zero;

        float speed = Mathf.Clamp01(apparentSpeed);
        float drawingAngle = Mathf.InverseLerp(
            25f, 45f, Mathf.Abs(windAngle));
        float error = sheetDeg - OptimalSheet(windAngle);
        float overEased = Mathf.Clamp01(error / 25f);
        float overTrimmed = Mathf.Clamp01(-error / 35f);
        float fill = speed * drawingAngle * (1f - overEased)
            * (1f - 0.45f * overTrimmed);
        float luff = speed * Mathf.Max(1f - drawingAngle, overEased);
        return new Vector2(fill, luff);
    }

    public static Vector2 RippleWeights(float luff, float phase)
    {
        luff = Mathf.Clamp01(luff);
        float wave = Mathf.Clamp(
            0.72f * Mathf.Sin(phase)
                + 0.28f * Mathf.Sin(1.73f * phase + 0.7f),
            -1f, 1f);
        return new Vector2(
            luff * Mathf.Max(0f, -wave),
            luff * Mathf.Max(0f, wave));
    }
}
