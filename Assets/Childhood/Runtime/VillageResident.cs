using System;
using UnityEngine;

namespace Childhood
{
    internal sealed class VillageResident
    {
        public const float RunSpeedMultiplier = 2.7f;
        private const float WalkingAcceleration = 3.5f;
        private const float BrakingAcceleration = 4f;
        private const float TurnSpeed = 300f;
        private readonly Transform root, door;
        private readonly float doorYaw;
        private readonly ChildLocomotion locomotion;
        private readonly ChildRigData rig;
        private readonly ResidentData data;
        private readonly CapsuleCollider capsule;
        private const float CryTime = 15f;
        private readonly bool child;
        private int stop;
        private float wait, opening, speed, crying;

        public Vector3 Position => root.position;
        public string DisplayName => $"{data.name}, {data.age} лет";
        public int MaxHealth => data.maxHealth > 0 ? data.maxHealth : 100;
        public bool CanSpar => child && crying <= 0f && IsPresent;
        public bool CanReprimand => !child && root.gameObject.activeInHierarchy;
        public bool IsPresent => root.gameObject.activeInHierarchy;
        public bool IsCrying => crying > 0f;
        public float Radius => .255f * data.scale[0];
        public float Height => (IsCrying ? .52f : 1.50f) * data.scale[1];
        public Func<Vector3, Vector3, bool> CanStep { get; set; }

        public void StartCrying()
        {
            crying = CryTime;
            capsule.height = .52f;
            capsule.center = Vector3.up * .26f;
        }
        public bool IsStriking => locomotion.IsStriking;
        public bool StrikeContact => locomotion.StrikeContact;
        public void Strike() => locomotion.Strike(false);
        public void ReactToHit() => locomotion.ReactToHit();

        public bool Faces(Vector3 target)
        {
            Vector3 direction = target - root.position;
            direction.y = 0f;
            return Vector3.Dot(root.forward, direction.normalized) >= .73f;
        }

        public void TickSpar(float dt, Vector3 target, Vector3 anchor, bool mayApproach, bool holds = false)
        {
            Vector3 direction = target - root.position;
            direction.y = 0f;
            float distance = direction.magnitude;
            locomotion.Guard(child);
            if (distance > .001f && !IsStriking)
                Face(Quaternion.LookRotation(direction), dt);
            float gap = Mathf.Max(0f, distance - .78f);
            float wanted = mayApproach && !IsStriking && !holds
                ? Mathf.Min(data.speed, 1.18f, Mathf.Sqrt(2f * BrakingAcceleration * gap)) : 0f;
            ChangeSpeed(wanted, dt);
            float step = mayApproach ? Mathf.Min(dt * speed, gap) : 0f;
            Vector3 next = root.position + direction.normalized * step;
            if ((next - anchor).sqrMagnitude < 2.7f * 2.7f && (CanStep == null || CanStep(root.position, next)))
                root.position = next;
            else
                step = 0f;
            locomotion.Tick(step / data.scale[1], dt, holds ? rig.reprimand : null);
        }

        public VillageResident(Transform root, Transform door, float doorYaw,
            ChildLocomotion locomotion, ChildRigData rig, ResidentData data)
        {
            this.root = root;
            capsule = root.GetComponent<CapsuleCollider>();
            this.door = door;
            this.doorYaw = doorYaw;
            this.locomotion = locomotion;
            this.rig = rig;
            this.data = data;
            child = data.door < 0;

            root.position = data.route[0].Position;
            wait = data.route[0].dwell;
            if (child)
            {
                Vector3 facing = data.route[1].Position - root.position;
                facing.y = 0f;
                if (facing.sqrMagnitude > .00001f)
                    root.rotation = Quaternion.LookRotation(facing);
            }
            root.gameObject.SetActive(!data.route[0].hidden);
            for (float elapsed = data.offset; elapsed > 0f; elapsed -= .10f)
                Tick(Mathf.Min(.10f, elapsed));
        }

        public void Tick(float dt)
        {
            locomotion.Guard(false);
            if (crying > 0f)
            {
                crying = Mathf.Max(0f, crying - dt);
                if (crying == 0f)
                {
                    capsule.height = 1.50f;
                    capsule.center = Vector3.up * .75f;
                }
                locomotion.SetCry(crying, CryTime);
                locomotion.Tick(0f, dt);
                return;
            }

            RouteStop current = data.route[stop];
            int next = (stop + 1) % data.route.Length;
            RouteStop destination = data.route[next];
            bool resting = wait > 0f;
            bool hidden = current.hidden && (resting || destination.hidden);
            root.gameObject.SetActive(!hidden);

            bool open = current.door || !resting && destination.door;
            if (door != null)
            {
                opening = Mathf.MoveTowards(opening, open ? 1f : 0f, dt * 2.6f);
                door.localRotation = Quaternion.Euler(0f, doorYaw + 91f * opening, 0f);
            }

            Vector3 initial = root.position;
            bool running = !resting && destination.run;
            GaitData activity = null;
            if (resting)
            {
                wait -= dt;
                speed = 0f;
                activity = rig.Activity(current.job);
                if (activity != null)
                    Face(Quaternion.Euler(0f, current.yaw, 0f), dt);
            }
            else
            {
                Vector3 target = destination.Position;
                Vector3 direction = target - initial;
                direction.y = 0f;
                float remaining = Vector3.Distance(initial, target);
                Vector3 forward = direction.normalized;
                float desiredSpeed = running ? data.speed * RunSpeedMultiplier : data.speed;
                RouteStop after = data.route[(next + 1) % data.route.Length];
                Vector3 exit = after.Position - target;
                exit.y = 0f;
                float alignment = Vector3.Dot(forward, exit.normalized);
                float exitSpeed = destination.dwell > 0f ? 0f : desiredSpeed * Mathf.InverseLerp(-.25f, .96f, alignment);
                if (direction.sqrMagnitude > .00001f)
                {
                    float lookAhead = .80f * Mathf.SmoothStep(0f, 1f, 1f - remaining / .60f);
                    Vector3 facing = destination.dwell <= 0f && alignment > -.7f
                        ? Vector3.Lerp(forward, exit.normalized, lookAhead) : forward;
                    Face(Quaternion.LookRotation(facing), dt);
                }
                float stoppingSpeed = Mathf.Sqrt(exitSpeed * exitSpeed + 2f * BrakingAcceleration * remaining);
                float turnFactor = direction.sqrMagnitude > .00001f
                    ? Mathf.Lerp(.30f, 1f, Mathf.InverseLerp(-.35f, .90f, Vector3.Dot(root.forward, forward))) : 1f;
                ChangeSpeed(Mathf.Min(desiredSpeed, stoppingSpeed) * turnFactor, dt);
                Vector3 proposed = Vector3.MoveTowards(initial, target, speed * dt);
                if (CanStep != null && !CanStep(initial, proposed))
                {
                    Vector3 side = Vector3.Cross(Vector3.up, forward) * speed * dt;
                    Vector3 slide = initial + (proposed - initial) * .45f + side * .67f;
                    if (CanStep(initial, slide) && !Physics.CheckSphere(slide + Vector3.up * .42f, Radius,
                            Walker.WorldMask, QueryTriggerInteraction.Ignore))
                        proposed = slide;
                    else
                        proposed = initial;
                }
                root.position = proposed;
                if (root.position == target)
                {
                    speed = Mathf.Min(speed, exitSpeed);
                    stop = next;
                    wait = destination.dwell;
                }
            }

            Vector3 moved = root.position - initial;
            moved.y = 0f;
            if (!hidden)
                locomotion.Tick(moved.magnitude / data.scale[1], dt, activity);
        }
        private void ChangeSpeed(float desired, float dt)
            => speed = Mathf.MoveTowards(speed, desired, (desired < speed ? BrakingAcceleration : WalkingAcceleration) * dt);

        private void Face(Quaternion goal, float dt)
        {
            float delta = Quaternion.Angle(root.rotation, goal);
            root.rotation = Quaternion.RotateTowards(root.rotation, goal, Mathf.Min(TurnSpeed * dt, delta * (1f - Mathf.Exp(-10f * dt))));
        }
    }
}
