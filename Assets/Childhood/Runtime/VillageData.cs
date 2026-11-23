using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Text;
using UnityEngine;
using UnityEngine.Rendering;

namespace Childhood
{
    [Serializable]
    internal sealed class VillageLayout
    {
        public float[] bounds;
        public float[] spawn;
        public float spawnYaw;
        public GateData[] gates;
        public StickData[] sticks;
        public DoorData[] doors;
        public ResidentData[] residents;
        public ChildRigData rig;
        public TreeData[] trees;
        public SolidData[] solids;
        public float[] catStops;
        public float catAlertRadius, catFleeSpeed;
        public CatPoint[] catPath;

        public static VillageLayout Read(TextAsset asset) => JsonUtility.FromJson<VillageLayout>(asset.text);
    }

    [Serializable]
    internal sealed class GateData
    {
        public float x, z, yaw, width;
        public string mesh;
    }

    [Serializable]
    internal sealed class StickData
    {
        public float[] point;
        public float yaw;
    }

    [Serializable]
    internal sealed class DoorData
    {
        public string mesh;
        public float[] point;
        public float yaw;
    }

    [Serializable]
    internal sealed class ResidentData
    {
        public string name, mesh, tool;
        public int door, age, maxHealth;
        public float[] scale;
        public float speed, offset;
        public RouteStop[] route;
    }

    [Serializable]
    internal sealed class RouteStop
    {
        public float[] point;
        public float dwell, yaw;
        public bool hidden, door, run;
        public string job;

        public Vector3 Position => new Vector3(point[0], point[1], point[2]);
    }

    [Serializable]
    internal sealed class TreeData
    {
        public string mesh;
        public int zone;
        public float[] placement;
    }

    [Serializable]
    internal sealed class SolidData
    {
        public float[] box;
        public bool vault;
    }

    [Serializable]
    internal sealed class CatPoint
    {
        public float x, z;
        public Vector3 Position => new Vector3(x, 0f, z);
    }

    [Serializable]
    internal sealed class ChildRigData
    {
        public BoneData[] bones;
        public float[] idle, crouchIdle, downPose, guardIdle;
        public GaitData walk, run, crouch, water, sweep, talk, reprimand, jump, vault;
        public GaitData palmStrike, stickStrike, guardWalk, guardSide;
        public float walkSpeed, runSpeed, crouchSpeed;

        public GaitData Activity(string job) => job switch
        {
            "water" => water,
            "sweep" => sweep,
            "talk" => talk,
            _ => null,
        };
    }

    [Serializable]
    internal sealed class BoneData
    {
        public string name;
        public int parent;
        public float[] offset;
    }

    [Serializable]
    internal sealed class GaitData
    {
        public float stride, contact;
        public GaitFrame[] frames;
    }

    [Serializable]
    internal sealed class GaitFrame
    {
        public float time;
        public float[] pose;
    }

    internal static class VillageMeshes
    {
        public const string Child = "Player character";

        public static Dictionary<string, Mesh> Read(TextAsset asset)
        {
            using var stream = new MemoryStream(asset.bytes);
            using var gzip = new GZipStream(stream, CompressionMode.Decompress);
            using var reader = new BinaryReader(gzip, Encoding.ASCII);
            if (Encoding.ASCII.GetString(reader.ReadBytes(4)) != "CDH5")
                throw new InvalidDataException("Unknown Childhood mesh format.");

            int meshCount = reader.ReadUInt16();
            var meshes = new Dictionary<string, Mesh>(meshCount);
            bool linear = QualitySettings.activeColorSpace == ColorSpace.Linear;
            for (int i = 0; i < meshCount; i++)
            {
                string name = Encoding.ASCII.GetString(reader.ReadBytes(reader.ReadByte()));
                int count = reader.ReadInt32();
                var vertices = new Vector3[count];
                var indices = new int[count];
                var colors = new Color[count];
                bool skinned = name == Child || name.StartsWith("Resident ", StringComparison.Ordinal);
                var uv = name == "Auto panels" || name.StartsWith("House skin ", StringComparison.Ordinal) ? new Vector2[count] : null;
                var normals = skinned ? new Vector3[count] : null;
                var weights = skinned ? new BoneWeight[count] : null;
                for (int vertex = 0; vertex < count; vertex++)
                {
                    vertices[vertex] = new Vector3(reader.ReadInt16(), reader.ReadInt16(), reader.ReadInt16()) * (skinned ? .001f : .01f);
                    Color color = new Color32(reader.ReadByte(), reader.ReadByte(), reader.ReadByte(), 255);
                    colors[vertex] = linear ? color.linear : color;
                    indices[vertex] = vertex;
                    if (uv != null)
                        uv[vertex] = new Vector2(reader.ReadUInt16(), reader.ReadUInt16()) / 65535f;
                    if (skinned)
                    {
                        normals[vertex] = new Vector3(reader.ReadSByte(), reader.ReadSByte(), reader.ReadSByte()).normalized;
                        int first = reader.ReadByte();
                        int second = reader.ReadByte();
                        float weight = reader.ReadByte() / 255f;
                        weights[vertex] = weight >= .5f
                            ? new BoneWeight { boneIndex0 = first, boneIndex1 = second, weight0 = weight, weight1 = 1f - weight }
                            : new BoneWeight { boneIndex0 = second, boneIndex1 = first, weight0 = 1f - weight, weight1 = weight };
                    }
                }

                var mesh = new Mesh { name = name, indexFormat = count > 65535 ? IndexFormat.UInt32 : IndexFormat.UInt16 };
                mesh.vertices = vertices;
                mesh.colors = colors;
                mesh.triangles = indices;
                if (uv != null) mesh.uv = uv;
                if (skinned)
                {
                    mesh.normals = normals;
                    mesh.boneWeights = weights;
                }
                else
                {
                    mesh.RecalculateNormals();
                }
                meshes.Add(name, mesh);
            }

            return meshes;
        }
    }
}
