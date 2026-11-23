using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace Childhood
{
    public sealed class VillageMorning : MonoBehaviour
    {
        [SerializeField] private Shader villageShader;
        [SerializeField] private Shader skyShader;
        [SerializeField] private Shader glassShader;
        [SerializeField] private TextAsset meshAsset;
        [SerializeField] private TextAsset layoutAsset;

        private VillageLayout layout;
        private Dictionary<string, Mesh> meshes;
        private Material material, skyMaterial, houseMaterial, carMaterial, autoPanelMaterial, carGlass;
        private Texture2D autoPanels, houseSurfaces;
        private readonly HashSet<Collider> vaultFences = new();
        private readonly List<Mesh> combinedMeshes = new();
        private readonly List<YardGate> gates = new();
        private Walker walker;
        private VillageCombat combat;
        private Transform heldStick;
        private Transform[] doors;
        private VillageResident[] residents;
        private VillageCat cat;
        private GUIStyle headingStyle, bodyStyle, promptStyle;
        private Texture2D panel;
        private bool intro = true;

        private void Awake()
        {
            layout = VillageLayout.Read(layoutAsset);
            meshes = VillageMeshes.Read(meshAsset);
            material = new Material(villageShader);
            houseSurfaces = LoadAtlas("HouseSurfaces", 256);
            houseMaterial = new Material(villageShader) { mainTexture = houseSurfaces };
            carMaterial = new Material(villageShader);
            carMaterial.SetFloat("_Surface", 2f);
            autoPanels = LoadAtlas("AutoPanels", 128);
            autoPanelMaterial = new Material(villageShader) { mainTexture = autoPanels };
            carGlass = new Material(glassShader);
            QualitySettings.shadowDistance = 43f;
            QualitySettings.shadowCascades = 2;
            QualitySettings.shadows = ShadowQuality.All;
            Application.targetFrameRate = 60;

            Color haze = new Color(.73f, .80f, .74f);
            ConfigureLight(haze);
            BuildScenery();
            walker = BuildPlayer(haze);
            cat = BuildCat();
            residents = BuildResidents();
            foreach (VillageResident resident in residents)
                resident.CanStep = (from, to) => ResidentMayStep(resident, from, to);
            AudioSource sobs = gameObject.AddComponent<AudioSource>();
            sobs.playOnAwake = false;
            combat = new VillageCombat(walker, residents, BuildSticks(), heldStick, sobs);
        }

        private static Texture2D LoadAtlas(string name, int size)
        {
            var texture = new Texture2D(size, size, TextureFormat.RGBA32, true)
            {
                wrapMode = TextureWrapMode.Clamp,
                filterMode = FilterMode.Trilinear,
            };
            texture.SetPixelData(Resources.Load<TextAsset>(name).bytes, 0);
            texture.Apply(true, true);
            return texture;
        }

        private void ConfigureLight(Color haze)
        {
            skyMaterial = new Material(skyShader);
            RenderSettings.skybox = skyMaterial;
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(.74f, .79f, .84f);
            RenderSettings.ambientEquatorColor = new Color(.68f, .68f, .59f);
            RenderSettings.ambientGroundColor = new Color(.49f, .47f, .34f);
            RenderSettings.ambientIntensity = 1.05f;
            RenderSettings.fog = true;
            RenderSettings.fogColor = haze;
            RenderSettings.fogMode = FogMode.Exponential;
            RenderSettings.fogDensity = .017f;

            Transform sun = MakeNode("Morning sun", transform);
            sun.rotation = Quaternion.LookRotation(new Vector3(.69f, -.58f, .43f));
            Light light = sun.gameObject.AddComponent<Light>();
            light.type = LightType.Directional;
            light.color = new Color(1f, .90f, .72f);
            light.intensity = 1.03f;
            light.shadows = LightShadows.Soft;
            light.shadowStrength = .74f;
            light.shadowBias = .055f;
            light.shadowNormalBias = .28f;
            RenderSettings.sun = light;
        }

        private void BuildScenery()
        {
            Transform scenery = MakeNode("Village", transform);
            foreach (var pair in meshes)
            {
                if (pair.Key.StartsWith("Gate ", StringComparison.Ordinal) ||
                    pair.Key.StartsWith("Door ", StringComparison.Ordinal) ||
                    pair.Key.StartsWith("Resident ", StringComparison.Ordinal) ||
                    pair.Key is "Watering can" or "Broom" or "Stick" ||
                    pair.Key.StartsWith("Player ", StringComparison.Ordinal) ||
                    pair.Key.StartsWith("Cat ", StringComparison.Ordinal) ||
                    pair.Key.StartsWith("Birch ", StringComparison.Ordinal) ||
                    pair.Key.StartsWith("Pine ", StringComparison.Ordinal))
                    continue;

                Transform piece = AddMesh(scenery, pair.Key);
                if (pair.Key is "01 Ground" or "02 Roads" or "ZAZ glass")
                    piece.GetComponent<MeshRenderer>().shadowCastingMode = ShadowCastingMode.Off;
            }

            var zones = new Dictionary<int, List<CombineInstance>>();
            foreach (TreeData tree in layout.trees)
            {
                if (!zones.TryGetValue(tree.zone, out var pieces))
                {
                    pieces = new List<CombineInstance>();
                    zones.Add(tree.zone, pieces);
                }

                float[] p = tree.placement;
                pieces.Add(new CombineInstance
                {
                    mesh = meshes[tree.mesh],
                    transform = Matrix4x4.TRS(new Vector3(p[0], 0f, p[1]),
                        Quaternion.Euler(0f, p[3], 0f), Vector3.one * p[2]),
                });
            }

            foreach (var zone in zones)
            {
                var grove = new Mesh { name = $"Grove {zone.Key}", indexFormat = IndexFormat.UInt32 };
                grove.CombineMeshes(zone.Value.ToArray());
                grove.UploadMeshData(true);
                combinedMeshes.Add(grove);
                AddMesh(scenery, grove);
            }

            Transform collision = MakeNode("Collision", transform);
            AddBox(collision, new Vector3(0f, -.25f, 9f), new Vector3(190f, .50f, 190f));
            foreach (SolidData solid in layout.solids)
            {
                float[] box = solid.box;
                BoxCollider obstacle = AddBox(collision, new Vector3(box[0], box[1], box[2]), new Vector3(box[3], box[4], box[5]));
                if (solid.vault)
                    vaultFences.Add(obstacle);
            }

            float[] b = layout.bounds;
            Vector3 center = new Vector3((b[0] + b[1]) / 2f, 2.5f, (b[2] + b[3]) / 2f);
            AddBox(collision, new Vector3(b[0] - .2f, center.y, center.z), new Vector3(.4f, 5f, b[3] - b[2] + 1f));
            AddBox(collision, new Vector3(b[1] + .2f, center.y, center.z), new Vector3(.4f, 5f, b[3] - b[2] + 1f));
            AddBox(collision, new Vector3(center.x, center.y, b[2] - .2f), new Vector3(b[1] - b[0] + 1f, 5f, .4f));
            AddBox(collision, new Vector3(center.x, center.y, b[3] + .2f), new Vector3(b[1] - b[0] + 1f, 5f, .4f));

            doors = new Transform[layout.doors.Length];
            for (int i = 0; i < doors.Length; i++)
            {
                DoorData data = layout.doors[i];
                float[] point = data.point;
                Transform door = MakeNode(data.mesh, scenery, new Vector3(point[0], point[1], point[2]));
                door.localRotation = Quaternion.Euler(0f, data.yaw, 0f);
                AddMesh(door, data.mesh);
                doors[i] = door;
            }

            foreach (GateData gate in layout.gates)
            {
                Transform hinge = MakeNode(gate.mesh, scenery, new Vector3(gate.x, 0f, gate.z));
                hinge.localRotation = Quaternion.Euler(0f, gate.yaw, 0f);
                Vector3 midpoint = hinge.TransformPoint(new Vector3(gate.width / 2f, 0f, 0f));
                AddMesh(hinge, gate.mesh);
                vaultFences.Add(AddBox(hinge, new Vector3(gate.width / 2f, .64f, 0f), new Vector3(gate.width, 1.28f, .16f)));
                gates.Add(new YardGate(hinge, gate, midpoint));
            }
        }

        private Walker BuildPlayer(Color haze)
        {
            float[] spawn = layout.spawn;
            Transform root = MakeNode("Player", transform, new Vector3(spawn[0], spawn[1], spawn[2]));
            CharacterController controller = root.gameObject.AddComponent<CharacterController>();
            controller.center = new Vector3(0f, .81f, 0f);
            controller.height = 1.62f;
            controller.radius = .25f;
            controller.stepOffset = .32f;
            controller.skinWidth = .028f;
            controller.minMoveDistance = 0f;
            root.gameObject.layer = 2;

            var person = BuildPerson(root, VillageMeshes.Child);
            Transform elbow = Array.Find(person.bones, bone => bone.name == "Right elbow");
            heldStick = MakeNode("Stick grip", elbow, new Vector3(0f, -.222f, .012f));
            heldStick.localRotation = Quaternion.Euler(4f, -71f, -10f);
            AddMesh(heldStick, "Stick", new Vector3(.255f, -.029f, 0f));
            heldStick.gameObject.SetActive(false);
            Camera camera = MakeNode("Third person camera", transform).gameObject.AddComponent<Camera>();
            camera.tag = "MainCamera";
            camera.clearFlags = CameraClearFlags.Skybox;
            camera.backgroundColor = haze;
            camera.fieldOfView = 57f;
            camera.nearClipPlane = .16f;
            camera.farClipPlane = 115f;
            camera.gameObject.AddComponent<AudioListener>();
            return new Walker(controller, person.body, person.locomotion, camera, layout.spawnYaw, vaultFences);
        }

        private (Transform body, Transform[] bones, ChildLocomotion locomotion) BuildPerson(Transform root, string meshName, float? walkPace = null, float? runPace = null)
        {
            Transform body = MakeNode(meshName, root);
            Mesh mesh = meshes[meshName];
            var bones = new Transform[layout.rig.bones.Length];
            var bindPoses = new Matrix4x4[bones.Length];
            for (int i = 0; i < bones.Length; i++)
            {
                BoneData bone = layout.rig.bones[i];
                float[] p = bone.offset;
                bones[i] = MakeNode(bone.name, bone.parent < 0 ? body : bones[bone.parent],
                    new Vector3(p[0], p[1], p[2]));
                bindPoses[i] = bones[i].worldToLocalMatrix * body.localToWorldMatrix;
            }

            mesh.bindposes = bindPoses;
            var model = body.gameObject.AddComponent<SkinnedMeshRenderer>();
            model.sharedMesh = mesh;
            model.sharedMaterial = material;
            model.bones = bones;
            model.rootBone = bones[0];
            model.localBounds = new Bounds(new Vector3(0f, .25f, 0f), new Vector3(1.7f, 2.5f, 1.7f));
            return (body, bones, new ChildLocomotion(layout.rig, bones, walkPace, runPace));

        }

        private VillageResident[] BuildResidents()
        {
            Transform neighborhood = MakeNode("Residents", transform);
            var result = new VillageResident[layout.residents.Length];
            for (int i = 0; i < result.Length; i++)
            {
                ResidentData data = layout.residents[i];
                Transform root = MakeNode(data.name, neighborhood);
                root.localScale = new Vector3(data.scale[0], data.scale[1], data.scale[2]);
                root.gameObject.layer = Walker.ResidentLayer;
                CapsuleCollider capsule = root.gameObject.AddComponent<CapsuleCollider>();
                capsule.radius = .255f;
                capsule.height = 1.5f;
                capsule.center = Vector3.up * .75f;
                float? walkPace = data.speed / data.scale[1];
                var person = BuildPerson(root, data.mesh, walkPace, walkPace * VillageResident.RunSpeedMultiplier);
                if (!string.IsNullOrEmpty(data.tool))
                {
                    Transform elbow = Array.Find(person.bones, bone => bone.name == "Right elbow");
                    AddMesh(elbow, data.tool, new Vector3(0f, -.214f, .020f));
                }
                Transform door = data.door >= 0 ? doors[data.door] : null;
                float doorYaw = data.door >= 0 ? layout.doors[data.door].yaw : 0f;
                result[i] = new VillageResident(root, door, doorYaw, person.locomotion, layout.rig, data);
            }
            return result;
        }

        private bool ResidentMayStep(VillageResident resident, Vector3 from, Vector3 to)
        {
            if (ApproachesPerson(from, to, resident.Height, walker.Position, walker.Height, resident.Radius + .25f))
                return false;
            foreach (VillageResident other in residents)
                if (other != resident && other.IsPresent && ApproachesPerson(from, to, resident.Height,
                        other.Position, other.Height, resident.Radius + other.Radius))
                    return false;
            return true;
        }

        private static bool ApproachesPerson(Vector3 from, Vector3 to, float height, Vector3 other, float otherHeight, float radius)
        {
            if (to.y >= other.y + otherHeight || to.y + height <= other.y)
                return false;
            from.y = to.y = other.y = 0f;
            float distance = (to - other).sqrMagnitude;
            return distance < radius * radius && distance < (from - other).sqrMagnitude;
        }

        private Transform[] BuildSticks()
        {
            Transform parent = MakeNode("Ground sticks", transform);
            var result = new Transform[layout.sticks.Length];
            for (int i = 0; i < result.Length; i++)
            {
                StickData stick = layout.sticks[i];
                float[] p = stick.point;
                result[i] = AddMesh(parent, "Stick", new Vector3(p[0], p[1], p[2]));
                result[i].localRotation = Quaternion.Euler(0f, stick.yaw, 0f);
            }
            return result;
        }

        private VillageCat BuildCat()
        {
            Transform root = MakeNode("Cat", transform);
            Transform body = AddMesh(root, "Cat body");
            Transform tail = AddMesh(body, "Cat tail", new Vector3(0f, .31f, -.27f));
            var legs = new Transform[4];
            for (int i = 0; i < legs.Length; i++)
            {
                float x = i % 2 == 0 ? -.083f : .083f;
                float z = i < 2 ? -.18f : .14f;
                legs[i] = AddMesh(body, "Cat leg", new Vector3(x, .201f, z));
            }
            return new VillageCat(root, body, tail, legs, layout);
        }

        private void Update()
        {
            bool locked = Cursor.lockState == CursorLockMode.Locked;
            if (locked && Input.GetKeyDown(KeyCode.Escape))
            {
                ReleaseMouse();
                locked = false;
            }
            else if (!locked && (Input.GetMouseButtonDown(0) || Input.GetKeyDown(KeyCode.Return)))
            {
                Cursor.lockState = CursorLockMode.Locked;
                Cursor.visible = false;
                intro = false;
            }

            walker.Tick(locked && combat.CanMove, combat.Opponent, combat.Equipped);
            if (locked && combat.CanMove)
            {
                if (Input.GetKeyDown(KeyCode.Alpha1)) combat.Equip(false);
                if (Input.GetKeyDown(KeyCode.Alpha2)) combat.Equip(true);
                if (Input.GetKeyDown(KeyCode.G)) combat.Drop();
                if (Input.GetKeyDown(KeyCode.E) && !combat.PickUp() && NearbyGate() is YardGate gate)
                    gate.Toggle(walker.Position);
                if (Input.GetKeyDown(KeyCode.F) || Input.GetMouseButtonDown(0))
                    combat.Attack();
            }
            combat.Tick(Time.deltaTime, locked);

            foreach (YardGate current in gates)
                current.Tick(walker.Position);
            cat.Tick(Time.deltaTime, walker.Position);
            foreach (VillageResident resident in residents)
                if (resident != combat.BusyResident)
                    resident.Tick(Time.deltaTime);
        }

        private YardGate NearbyGate()
        {
            YardGate closest = null;
            float closestDistance = 1.72f * 1.72f;
            foreach (YardGate gate in gates)
            {
                Vector3 delta = gate.Midpoint - walker.Position;
                delta.y = 0f;
                if (delta.sqrMagnitude >= closestDistance)
                    continue;
                closest = gate;
                closestDistance = delta.sqrMagnitude;
            }
            return closest;
        }

        private void LateUpdate() => walker.TickCamera(Time.deltaTime);

        private void OnGUI()
        {
            InitGui();
            float scale = Mathf.Clamp(Screen.height / 850f, .68f, 1.35f);
            Matrix4x4 original = GUI.matrix;
            GUI.matrix = Matrix4x4.Scale(new Vector3(scale, scale, 1f));
            float width = Screen.width / scale;
            float height = Screen.height / scale;
            bool locked = Cursor.lockState == CursorLockMode.Locked;

            if (!locked)
            {
                float cardWidth = Mathf.Min(448f, width - 48f);
                Rect card = new Rect(34f, height - 169f, cardWidth, 131f);
                GUI.DrawTexture(card, panel);
                GUI.Label(new Rect(card.x + 19f, card.y + 12f, card.width - 32f, 41f),
                    intro ? "Утро на даче" : "Прогулка на паузе", headingStyle);
                GUI.Label(new Rect(card.x + 20f, card.y + 58f, card.width - 36f, 52f),
                    "Нажми, чтобы гулять\nWASD — идти   Shift — бег   C — присесть\nПробел — прыжок   F — удар   E — подобрать / открыть   G — выбросить", bodyStyle);
            }
            else
            {
                DrawBar(26f, 25f, "Здоровье", combat.Equipped ? "Палка" : "Ладонь", combat.Health);
                if (combat.Opponent != null)
                    DrawBar(width - 206f, 25f, combat.Opponent.DisplayName, "", combat.OpponentHealth, combat.Opponent.MaxHealth);

                string message = null;
                if (combat.IsCrying)
                    message = "Ты расплакался…";
                else if (combat.IsReprimanding)
                    message = "Взрослый поймал тебя";
                else if (combat.NearbyStick() != null)
                    message = "E   Подобрать палку";
                else if (NearbyGate() is YardGate gate)
                    message = gate.IsOpen ? "E   Закрыть калитку" : "E   Открыть калитку";

                if (message != null)
                {
                    Rect hint = new Rect(width / 2f - 120f, height - 96f, 240f, 46f);
                    GUI.DrawTexture(hint, panel);
                    GUI.Label(hint, message, promptStyle);
                }
            }
            GUI.matrix = original;
        }

        private void DrawBar(float x, float y, string label, string detail, int value, int max = 100)
        {
            GUI.DrawTexture(new Rect(x, y, 180f, 64f), panel);
            GUI.Label(new Rect(x + 12f, y + 5f, 156f, 19f), label, bodyStyle);
            Color previous = GUI.color;
            GUI.color = new Color(.29f, .32f, .24f);
            GUI.DrawTexture(new Rect(x + 12f, y + 26f, 156f, 7f), Texture2D.whiteTexture);
            GUI.color = new Color(.58f, .68f, .42f);
            if (value > 0)
                GUI.DrawTexture(new Rect(x + 12f, y + 26f, 156f * value / max, 7f), Texture2D.whiteTexture);
            GUI.color = previous;
            string status = string.IsNullOrEmpty(detail) ? $"{value} / {max}" : $"{value}  {detail}";
            GUI.Label(new Rect(x + 12f, y + 37f, 156f, 21f), status, bodyStyle);
        }

        private void InitGui()
        {
            if (panel != null)
                return;
            panel = new Texture2D(1, 1);
            panel.SetPixel(0, 0, new Color(.15f, .20f, .14f, .91f));
            panel.Apply();
            headingStyle = new GUIStyle(GUI.skin.label) { fontSize = 28, fontStyle = FontStyle.Bold };
            bodyStyle = new GUIStyle(GUI.skin.label) { fontSize = 14, wordWrap = true };
            promptStyle = new GUIStyle(bodyStyle) { alignment = TextAnchor.MiddleCenter };
            headingStyle.normal.textColor = new Color(.99f, .94f, .81f);
            bodyStyle.normal.textColor = headingStyle.normal.textColor;
            promptStyle.normal.textColor = headingStyle.normal.textColor;
        }

        private void OnApplicationFocus(bool focus)
        {
            if (!focus && Cursor.lockState == CursorLockMode.Locked)
                ReleaseMouse();
        }

        private void OnDisable()
        {
            if (Cursor.lockState == CursorLockMode.Locked)
                ReleaseMouse();
        }

        private void OnDestroy()
        {
            if (meshes != null)
                foreach (Mesh mesh in meshes.Values)
                    Destroy(mesh);
            foreach (Mesh mesh in combinedMeshes)
                Destroy(mesh);
            if (material != null)
                Destroy(material);
            if (houseMaterial != null)
                Destroy(houseMaterial);
            if (carMaterial != null)
                Destroy(carMaterial);
            if (houseSurfaces != null)
                Destroy(houseSurfaces);
            if (carGlass != null)
                Destroy(carGlass);
            if (autoPanelMaterial != null)
                Destroy(autoPanelMaterial);
            if (autoPanels != null)
                Destroy(autoPanels);
            if (skyMaterial != null)
                Destroy(skyMaterial);
            if (panel != null)
                Destroy(panel);
        }

        private static void ReleaseMouse()
        {
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
        }

        private Transform AddMesh(Transform parent, string name, Vector3 offset = default)
            => AddMesh(parent, meshes[name], offset);

        private Transform AddMesh(Transform parent, Mesh mesh, Vector3 offset = default)
        {
            Transform node = MakeNode(mesh.name, parent, offset);
            node.gameObject.AddComponent<MeshFilter>().sharedMesh = mesh;
            node.gameObject.AddComponent<MeshRenderer>().sharedMaterial =
                mesh.name == "Auto panels" ? autoPanelMaterial :
                mesh.name.StartsWith("House skin ", StringComparison.Ordinal) ? houseMaterial :
                mesh.name == "ZAZ glass" ? carGlass :
                mesh.name.StartsWith("Car ", StringComparison.Ordinal) ? carMaterial : material;
            return node;
        }

        private static Transform MakeNode(string name, Transform parent, Vector3 offset = default)
        {
            Transform node = new GameObject(name).transform;
            node.SetParent(parent, false);
            node.localPosition = offset;
            return node;
        }

        private static BoxCollider AddBox(Transform parent, Vector3 center, Vector3 size)
        {
            BoxCollider box = parent.gameObject.AddComponent<BoxCollider>();
            box.center = center;
            box.size = size;
            return box;
        }
    }
}
