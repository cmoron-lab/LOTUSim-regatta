// Copyright (c) 2026 Cyril Moron — EPL-2.0
using System.Reflection;
using UnityEngine;
using NUnit.Framework;

public class WakeMathTests
{
    const float RefSpeed = 0.5f;
    const float Eps = 1e-4f;

    [TestCase(0f, 0f)]
    [TestCase(0.25f, 0.5f)]
    [TestCase(0.5f, 1f)]
    [TestCase(5f, 1f)]
    public void SpeedFactorIsClamped(float speed, float expected)
    {
        Assert.AreEqual(expected, WakeMath.SpeedFactor(speed, RefSpeed), Eps);
    }

    [TestCase(0.11f, 0.12f, 0.5f, 0.03f, false)]
    [TestCase(0.12f, 0.12f, 0.02f, 0.03f, false)]
    [TestCase(0.12f, 0.12f, 0.03f, 0.03f, true)]
    public void EmissionRequiresDistanceAndSpeed(
        float distance, float spacing, float speed, float minSpeed, bool expected)
    {
        Assert.AreEqual(
            expected, WakeMath.ShouldEmit(distance, spacing, speed, minSpeed));
    }

    [Test]
    public void PairedStampsDivergeFromTheirSharedOrigin()
    {
        Vector3 origin = new Vector3(3f, 0f, 4f);
        Vector3 right = Vector3.right;

        Vector3 starboard =
            WakeMath.StampPosition(origin, right, 1, 3f, 2f, 45f);
        Vector3 port =
            WakeMath.StampPosition(origin, right, -1, 3f, 2f, 45f);

        Assert.AreEqual(9f, starboard.x, Eps);
        Assert.AreEqual(-3f, port.x, Eps);
        Assert.AreEqual(origin.y, starboard.y, Eps);
        Assert.AreEqual(origin.z, starboard.z, Eps);
    }

    [TestCase(0f, 5f, 1f)]
    [TestCase(2.5f, 5f, 0.5f)]
    [TestCase(5f, 5f, 0f)]
    [TestCase(10f, 5f, 0f)]
    public void FadeDecreasesOverLifetime(
        float age, float lifetime, float expected)
    {
        Assert.AreEqual(expected, WakeMath.Fade(age, lifetime), Eps);
    }

    [Test]
    public void InvalidCalibrationDisablesWake()
    {
        Assert.AreEqual(0f, WakeMath.SpeedFactor(1f, 0f), Eps);
        Assert.IsFalse(WakeMath.ShouldEmit(1f, 0f, 1f, 0f));
        Assert.AreEqual(0f, WakeMath.LateralOffset(1f, 1f, 90f), Eps);
        Assert.AreEqual(0f, WakeMath.Fade(0f, 0f), Eps);
    }

    [TestCase(0, 48, 1)]
    [TestCase(47, 48, 0)]
    [TestCase(4, 0, 0)]
    public void PairIndexWrapsInsidePool(int current, int capacity, int expected)
    {
        Assert.AreEqual(expected, WakeMath.NextPairIndex(current, capacity));
    }
}

public class ManualHelmDecisionTests
{
    static bool Decision(string name, params object[] args)
    {
        System.Type manualHelm =
            System.Type.GetType("ManualHelm, Assembly-CSharp");
        Assert.IsNotNull(manualHelm);
        MethodInfo method = manualHelm.GetMethod(
            name, BindingFlags.NonPublic | BindingFlags.Static);
        Assert.IsNotNull(method);
        return (bool)method.Invoke(null, args);
    }

    [TestCase(0f, 0.35f, false)]
    [TestCase(0.35f, 0.35f, false)]
    [TestCase(0.36f, 0.35f, true)]
    public void CalibrationRequiresAControlStillHeld(
        float excursion, float trigger, bool expected)
    {
        Assert.AreEqual(
            expected,
            Decision("CalibrationCandidateIsHeld", excursion, trigger));
    }

    [TestCase(false, "", 1f, 1f, true)]
    [TestCase(true, "", 0f, 0f, false)]
    [TestCase(true, "axis", 0f, 1f, true)]
    [TestCase(true, "axis", 1f, 0f, true)]
    [TestCase(true, "axis", 1f, 1f, false)]
    public void DefaultBindingDistinguishesAbsentAndExplicitlyUnbound(
        bool saved, string path, float sign, float span, bool expected)
    {
        Assert.AreEqual(
            expected,
            Decision(
                "ShouldUseDefaultBinding", saved, path, sign, span));
    }
}
