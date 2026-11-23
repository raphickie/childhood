using System;
using UnityEngine;

namespace Childhood
{
    internal sealed class ChildLocomotion
    {
        private readonly ChildRigData rig;
        private readonly Transform[] bones;
        private readonly Vector3 hips;
        private readonly float walkSpeed, runSpeed;
        private float phase, moving, sprint, crouch, strikeTime, guard, strafe;
        private bool guarding, armed;
        private readonly int chest, shoulder, elbow, head;
        private readonly Transform eyes, leftHand, rightHand;
        private readonly bool[] upperBody;
        private float time, leapPhase, leapWeight, reprimand, flinch;
        private GaitData leap, strike;
        public bool IsStriking => strike != null;
        public bool StrikeContact { get; private set; }
        public const float CryDuration = 4f;
        public float CryAmount { get; private set; }
        private float sob;
        private GaitData activity;
        private float activityPhase, activityWeight;

        public ChildLocomotion(ChildRigData rig, Transform[] bones, float? walkPace = null, float? runPace = null)
        {
            this.rig = rig;
            this.bones = bones;
            walkSpeed = walkPace ?? rig.walkSpeed;
            runSpeed = runPace ?? rig.runSpeed;
            hips = bones[0].localPosition;
            head = Array.FindIndex(bones, bone => bone.name == "Head");
            eyes = Array.Find(bones, bone => bone.name == "Eyes");
            chest = Array.FindIndex(bones, bone => bone.name == "Chest");
            shoulder = Array.FindIndex(bones, bone => bone.name == "Right shoulder");
            elbow = Array.FindIndex(bones, bone => bone.name == "Right elbow");
            leftHand = Array.Find(bones, bone => bone.name == "Left hand");
            rightHand = Array.Find(bones, bone => bone.name == "Right hand");
            upperBody = Array.ConvertAll(bones, bone => bone.name == "Chest" || bone.name == "Head" ||
                bone.name.EndsWith(" shoulder", StringComparison.Ordinal) || bone.name.EndsWith(" elbow", StringComparison.Ordinal));
            ApplyPose();
        }

        public float Speed(bool running, bool low = false) => low ? rig.crouchSpeed : running ? runSpeed : walkSpeed;

        public void Strike(bool withStick)
        {
            strike = withStick ? rig.stickStrike : rig.palmStrike;
            strikeTime = 0f;
            StrikeContact = false;
        }

        public void Guard(bool enabled, bool withStick = false)
        {
            guarding = enabled;
            armed = withStick;
        }

        public void ReactToHit() => flinch = 1f;

        public void SetCry(float remaining, float duration = CryDuration)
        {
            float elapsed = duration - remaining;
            CryAmount = Mathf.SmoothStep(0f, 1f, Mathf.Min(elapsed / .34f, remaining / .58f));
            sob = Mathf.Sin(elapsed * 27f) * CryAmount;
        }

        public void SetLeap(float progress, bool vault)
        {
            leap = vault ? rig.vault : rig.jump;
            leapPhase = Mathf.Clamp01(progress);
            leapWeight = Mathf.Clamp01(Mathf.Min(leapPhase / .14f, (1f - leapPhase) / .17f));
        }

        public void SetReprimand(bool caught, bool hit = false)
        {
            reprimand = caught ? 1f : 0f;
            if (hit)
                flinch = 1f;
        }

        public void Tick(float distance, float dt, GaitData nextActivity = null, bool low = false, bool backwards = false, float sideways = 0f)
        {
            time += dt;
            float blend = 1f - Mathf.Exp(-11f * dt);
            float amount = Mathf.Clamp01(distance / Mathf.Max(.0001f, dt * (guarding ? 1.18f : low ? rig.crouchSpeed : walkSpeed)));
            moving = Mathf.Lerp(moving, amount, blend);
            float runWeight = Mathf.InverseLerp(walkSpeed, runSpeed, distance / Mathf.Max(.0001f, dt));
            sprint = Mathf.Lerp(sprint, runWeight, blend);
            crouch = Mathf.Lerp(crouch, low ? 1f : 0f, blend);
            guard = Mathf.Lerp(guard, guarding && CryAmount < .05f ? 1f : 0f, blend);
            strafe = Mathf.Lerp(strafe, sideways, blend);
            float stride = Mathf.Lerp(Mathf.Lerp(Mathf.Lerp(rig.walk.stride, rig.run.stride, sprint),
                rig.crouch.stride, crouch), Mathf.Lerp(rig.guardWalk.stride, rig.guardSide.stride, strafe), guard);
            phase = Mathf.Repeat(phase + (backwards ? -distance : distance) / stride, 1f);
            StrikeContact = false;
            if (strike != null)
            {
                StrikeContact = strikeTime < strike.contact && strikeTime + dt >= strike.contact;
                strikeTime += dt;
                if (strikeTime >= strike.stride)
                    strike = null;
            }
            flinch = Mathf.Max(0f, flinch - dt / .23f);

            if (nextActivity != null && (activity != nextActivity || activityWeight == 0f))
            {
                activity = nextActivity;
                activityPhase = 0f;
            }
            activityWeight = Mathf.MoveTowards(activityWeight, nextActivity == null ? 0f : 1f, dt * 4f);
            if (activityWeight > 0f)
                activityPhase = Mathf.Repeat(activityPhase + dt / activity.stride, 1f);
            ApplyPose();
        }

        private void ApplyPose()
        {
            float breathe = Mathf.Sin(time * 2.3f) * (1f - moving) * (1f - CryAmount) * (1f - leapWeight);
            float recoil = Mathf.Pow(Mathf.Sin(Mathf.PI * flinch), 2f) * (1f - CryAmount);
            bones[0].localPosition = hips + Vector3.up * (Channel(0) + breathe * .003f);
            float blink = Mathf.Abs(Mathf.Repeat(time + walkSpeed * .71f, 3.9f) - 1.8f);
            if (eyes != null)
                eyes.localScale = new Vector3(1f, Mathf.Lerp(Mathf.Clamp01(.12f + blink * 11f), .08f, CryAmount), 1f);
            float progress = strike == null ? 0f : strikeTime / strike.stride;
            float attackWeight = Mathf.SmoothStep(0f, 1f, Mathf.Min(progress, 1f - progress) / .18f) * (1f - CryAmount);
            float grip = Mathf.Max(guard, attackWeight) * (1f - CryAmount);
            Vector3 handScale = new Vector3(1f + .16f * grip, 1f - .26f * grip, 1f + .17f * grip);
            leftHand.localScale = handScale;
            rightHand.localScale = handScale;
            for (int i = 0; i < bones.Length; i++)
            {
                int channel = i * 3 + 1;
                float x = Channel(channel);
                float y = Channel(channel + 1);
                float z = Channel(channel + 2);
                if (armed && i == shoulder)
                {
                    x += 15f * guard;
                    y -= 17f * guard;
                    z += 13f * guard;
                }
                if (armed && i == elbow)
                    x += 19f * guard;
                if (attackWeight > 0f && upperBody[i])
                {
                    x = Mathf.Lerp(x, SampleStrike(progress, channel), attackWeight);
                    y = Mathf.Lerp(y, SampleStrike(progress, channel + 1), attackWeight);
                    z = Mathf.Lerp(z, SampleStrike(progress, channel + 2), attackWeight);
                }
                if (i == chest)
                {
                    x += 3.2f * sob + breathe * 1.05f + (reprimand > 0f ? 15f : -12f) * recoil;
                    z += 5f * recoil;
                }
                if (i == head)
                {
                    x += 8f * reprimand;
                    z += 11f * reprimand;
                }
                bones[i].localRotation = Quaternion.Euler(x, y, z);
            }
        }

        private float Channel(int index)
        {
            float value = rig.idle[index];
            if (moving > .001f)
                value = Mathf.Lerp(value, Mathf.Lerp(Sample(rig.walk, phase, index), Sample(rig.run, phase, index), sprint), moving);
            if (crouch > .001f)
                value = Mathf.Lerp(value, Mathf.Lerp(rig.crouchIdle[index], Sample(rig.crouch, phase, index), moving), crouch);
            if (guard > .001f)
                value = Mathf.Lerp(value, Mathf.Lerp(rig.guardIdle[index], Mathf.Lerp(Sample(rig.guardWalk, phase, index),
                    Sample(rig.guardSide, phase, index), strafe), moving), guard);
            if (activityWeight > 0f)
                value = Mathf.Lerp(value, Sample(activity, activityPhase, index), activityWeight);
            if (leapWeight > 0f)
            {
                float t = leapPhase * (leap.frames.Length - 1);
                int frame = Mathf.Min((int)t, leap.frames.Length - 2);
                float mix = Mathf.SmoothStep(0f, 1f, t - frame);
                value = Mathf.Lerp(value, Mathf.Lerp(leap.frames[frame].pose[index],
                    leap.frames[frame + 1].pose[index], mix), leapWeight);
            }
            return Mathf.Lerp(value, rig.downPose[index], CryAmount);
        }

        private float SampleStrike(float progress, int index)
        {
            GaitFrame[] keys = strike.frames;
            int i = 0;
            while (i < keys.Length - 2 && keys[i + 1].time < progress)
                i++;
            float t = Mathf.InverseLerp(keys[i].time, keys[i + 1].time, progress);
            // Keep the striking hand moving through the contact key.
            float a = keys[i].pose[index], b = keys[i + 1].pose[index];
            float segment = keys[i + 1].time - keys[i].time;
            float m0 = SlopeAt(keys, i, index) * segment;
            float m1 = SlopeAt(keys, i + 1, index) * segment;
            return a + t * (m0 + t * (3f * (b - a) - 2f * m0 - m1 + t * (2f * (a - b) + m0 + m1)));
        }

        private static float SlopeAt(GaitFrame[] keys, int i, int index)
        {
            if (i == 0 || i == keys.Length - 1)
                return 0f;
            float before = (keys[i].pose[index] - keys[i - 1].pose[index]) / (keys[i].time - keys[i - 1].time);
            float after = (keys[i + 1].pose[index] - keys[i].pose[index]) / (keys[i + 1].time - keys[i].time);
            return before * after <= 0f ? 0f : 2f * before * after / (before + after);
        }

        private static float Sample(GaitData gait, float cycle, int index)
        {
            int length = gait.frames.Length;
            float frame = cycle * length;
            int a = Mathf.FloorToInt(frame);
            float t = frame - a;
            float previous = gait.frames[(a + length - 1) % length].pose[index];
            float start = gait.frames[a].pose[index];
            float end = gait.frames[(a + 1) % length].pose[index];
            float after = gait.frames[(a + 2) % length].pose[index];
            float m0 = (end - previous) * .5f;
            float m1 = (after - start) * .5f;
            return start + t * (m0 + t * (3f * (end - start) - 2f * m0 - m1
                + t * (2f * (start - end) + m0 + m1)));
        }
    }
}
