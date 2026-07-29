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

    [TestCase(0f, 0f)]
    [TestCase(0.25f, 0.25f)]
    [TestCase(0.5f, 1f)]
    [TestCase(5f, 1f)]
    public void WakeStrengthUsesQuadraticSpeedResponse(
        float speed, float expected)
    {
        Assert.AreEqual(
            expected, WakeMath.WakeStrength(speed, RefSpeed), Eps);
    }

    [TestCase(0f, 0.35f)]
    [TestCase(0.25f, 1.675f)]
    [TestCase(0.5f, 3f)]
    [TestCase(5f, 3f)]
    public void WakeLengthScalesWithSpeed(float speed, float expected)
    {
        Assert.AreEqual(
            expected,
            WakeMath.WakeLength(speed, RefSpeed, 0.35f, 3f),
            Eps);
    }

    [TestCase(0f, 0f)]
    [TestCase(0.1f, 0.25f)]
    [TestCase(0.8f, 0.5123f)]
    [TestCase(2f, 0.8f)]
    public void WakePeriodFollowsDeepWaterDispersion(
        float speed, float expected)
    {
        Assert.AreEqual(
            expected, WakeMath.WakePeriod(speed, 0.25f, 0.8f), Eps);
    }

    [TestCase(0f, 0.02f, 0.25f, 0f)]
    [TestCase(0.01f, 0.02f, 0.25f, 0.5f)]
    [TestCase(0.3f, 0.02f, 0.25f, 0f)]
    [TestCase(0.01f, 0f, 0.25f, 0f)]
    public void MotionSpeedRejectsInvalidAndTeleportSteps(
        float distance, float deltaTime, float maxStep, float expected)
    {
        Assert.AreEqual(
            expected,
            WakeMath.MotionSpeed(distance, deltaTime, maxStep),
            Eps);
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

[TestFixture]
public class SailVisualMathTests
{
    const float Eps = 1e-4f;

    [Test]
    public void ApparentWindSubtractsBoatVelocity()
    {
        Assert.AreEqual(
            new Vector3(-0.5f, 0f, -3f),
            SailVisualMath.ApparentWind(
                new Vector3(0f, 0f, -3f),
                new Vector3(0.5f, 0f, 0f)));
    }

    [TestCase(3f, -1f, -1f)]
    [TestCase(-3f, 1f, 1f)]
    [TestCase(179f, -1f, -1f)]
    [TestCase(-179f, 1f, 1f)]
    [TestCase(60f, -1f, 1f)]
    [TestCase(-60f, 1f, -1f)]
    public void SailSideChangesOnlyAtStableAngles(
        float windAngle, float lastSide, float expected)
    {
        Assert.AreEqual(
            expected, SailVisualMath.StableSide(windAngle, lastSide));
    }

    [Test]
    public void CorrectlyTrimmedSailFills()
    {
        Vector2 state = SailVisualMath.Response(
            3f, 60f, SailVisualMath.OptimalSheet(60f));
        Assert.Greater(state.x, 0.95f);
        Assert.Less(state.y, Eps);
    }

    [TestCase(5f, 4f)]
    [TestCase(60f, 70f)]
    public void HeadToWindOrOverEasedSailLuffs(float angle, float sheet)
    {
        Vector2 state = SailVisualMath.Response(3f, angle, sheet);
        Assert.Less(state.x, 0.05f);
        Assert.Greater(state.y, 0.95f);
    }

    [Test]
    public void NoWindProducesNoDeformation()
    {
        Assert.AreEqual(Vector2.zero,
            SailVisualMath.Response(0f, 60f, 11f));
    }

    [Test]
    public void DownwindTrimStaysFilled()
    {
        Vector2 state = SailVisualMath.Response(3f, 180f, 80f);
        Assert.Greater(state.x, 0.95f);
        Assert.Less(state.y, Eps);
    }

    [Test]
    public void RippleWeightsStayBoundedByLuff()
    {
        for (int i = 0; i < 100; ++i)
        {
            Vector2 weights = SailVisualMath.RippleWeights(0.6f, i * 0.2f);
            Assert.That(weights.x, Is.InRange(0f, 0.6f));
            Assert.That(weights.y, Is.InRange(0f, 0.6f));
        }
    }
}
