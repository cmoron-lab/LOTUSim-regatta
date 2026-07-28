// Copyright (c) 2026 Cyril Moron — EPL-2.0
using NUnit.Framework;

public class WakeMathTests
{
    const float RefSpeed = 0.5f;
    const float MaxWidth = 0.3f;
    const float Eps = 1e-4f;

    [TestCase(0f, 0f)]
    [TestCase(0.25f, 0.5f)]
    [TestCase(0.5f, 1f)]
    [TestCase(5f, 1f)]
    public void SpeedFactorIsClamped(float speed, float expected)
    {
        Assert.AreEqual(expected, WakeMath.SpeedFactor(speed, RefSpeed), Eps);
    }

    [TestCase(0f, 0f)]
    [TestCase(0.25f, 0.15f)]
    [TestCase(0.5f, 0.3f)]
    [TestCase(5f, 0.3f)]
    public void WakeWidthTracksMeasuredSpeed(float speed, float expected)
    {
        Assert.AreEqual(expected,
                        WakeMath.WakeWidth(speed, RefSpeed, MaxWidth), Eps);
    }

    [Test]
    public void InvalidCalibrationDisablesWidth()
    {
        Assert.AreEqual(0f, WakeMath.SpeedFactor(1f, 0f), Eps);
        Assert.AreEqual(0f, WakeMath.WakeWidth(1f, RefSpeed, 0f), Eps);
    }
}
