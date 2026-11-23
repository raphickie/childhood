using UnityEngine;

namespace Childhood
{
    internal sealed class YardGate
    {
        private readonly Transform hinge;
        private readonly GateData data;
        private float rotation;
        public Vector3 Midpoint { get; }
        public bool IsOpen { get; private set; }

        public YardGate(Transform hinge, GateData data, Vector3 midpoint)
        {
            this.hinge = hinge;
            this.data = data;
            Midpoint = midpoint;
        }

        public void Toggle(Vector3 player)
        {
            if (IsOpen && PlayerClearance(data.yaw, player) < .36f * .36f)
                return;
            IsOpen = !IsOpen;
        }

        public void Tick(Vector3 player)
        {
            float destination = IsOpen ? -98f : 0f;
            float next = Mathf.MoveTowards(rotation, destination, 215f * Time.deltaTime);
            if (Mathf.Approximately(next, rotation))
                return;
            float clearance = PlayerClearance(data.yaw + next, player);
            if (clearance < .36f * .36f && clearance < PlayerClearance(data.yaw + rotation, player))
                return;

            rotation = next;
            hinge.localRotation = Quaternion.Euler(0f, data.yaw + rotation, 0f);
        }

        private float PlayerClearance(float yaw, Vector3 player)
        {
            Vector3 fromHinge = player - hinge.position;
            if (fromHinge.y > 1.28f)
                return float.PositiveInfinity;

            fromHinge.y = 0f;
            Vector3 direction = Quaternion.Euler(0f, yaw, 0f) * Vector3.right;
            float nearest = Mathf.Clamp(Vector3.Dot(fromHinge, direction), 0f, data.width);
            return (fromHinge - direction * nearest).sqrMagnitude;
        }
    }

    internal sealed class VillageCat
    {
        private readonly Transform root, body, tail;
        private readonly Transform[] legs;
        private readonly VillageLayout layout;
        private readonly CatPoint[] waypoints;
        private int next = 1, routeStep = 1;
        private float wait, stride, time, alarm;

        public VillageCat(Transform root, Transform body, Transform tail, Transform[] legs, VillageLayout layout)
        {
            this.root = root;
            this.body = body;
            this.tail = tail;
            this.legs = legs;
            this.layout = layout;
            waypoints = layout.catPath;
            root.position = waypoints[0].Position;
            root.rotation = Quaternion.LookRotation(waypoints[1].Position - root.position);
            wait = layout.catStops[0];
        }

        public void Tick(float dt, Vector3 player)
        {
            time += dt;
            Vector3 away = root.position - player;
            away.y = 0f;
            alarm = Mathf.Max(0f, alarm - dt);
            if (away.sqrMagnitude < layout.catAlertRadius * layout.catAlertRadius)
            {
                TurnAway(away);
                alarm = 1.30f;
                wait = 0f;
            }
            bool fleeing = alarm > 0f;
            float movement = 0f;
            if (wait > 0)
            {
                wait -= dt;
            }
            else
            {
                Vector3 target = waypoints[next].Position;
                Vector3 direction = target - root.position;
                if (direction.sqrMagnitude < .0025f)
                {
                    wait = fleeing ? 0f : layout.catStops[next];
                    next = Wrap(next + routeStep);
                }
                else
                {
                    Vector3 previous = root.position;
                    root.rotation = Quaternion.RotateTowards(root.rotation, Quaternion.LookRotation(direction),
                        (fleeing ? 950f : 350f) * dt);
                    root.position = Vector3.MoveTowards(previous, target, (fleeing ? layout.catFleeSpeed : 1.07f) * dt);
                    movement = (root.position - previous).magnitude;
                }
            }

            stride += movement * (fleeing ? 10f : 16f);
            float swing = movement > 0f ? Mathf.Sin(stride) * (fleeing ? 48f : 32f) : 0f;
            for (int i = 0; i < legs.Length; i++)
            {
                float diagonal = fleeing ? (i < 2 ? 1f : -1f) : (i == 0 || i == 3 ? 1f : -1f);
                legs[i].localRotation = Quaternion.Slerp(legs[i].localRotation,
                    Quaternion.Euler(diagonal * swing, 0f, 0f), 15f * dt);
            }
            body.localPosition = Vector3.up * (movement > 0f
                ? (fleeing ? .055f : .018f) * Mathf.Abs(Mathf.Cos(stride)) : 0f);
            tail.localRotation = Quaternion.Euler(0f, 19f * Mathf.Sin(time * 2.7f), 9f * Mathf.Sin(time * 1.8f));
        }
        private int Wrap(int index) => (index + waypoints.Length) % waypoints.Length;

        private void TurnAway(Vector3 away)
        {
            int previous = Wrap(next - routeStep);
            if ((waypoints[previous].Position - root.position).sqrMagnitude < .0144f)
                previous = Wrap(previous - routeStep);
            float forward = Vector3.Dot((waypoints[next].Position - root.position).normalized, away);
            float backward = Vector3.Dot((waypoints[previous].Position - root.position).normalized, away);
            if (backward > forward + .08f)
            {
                routeStep = -routeStep;
                next = previous;
            }
        }
    }
}
