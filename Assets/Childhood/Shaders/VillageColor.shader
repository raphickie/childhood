Shader "Childhood/VillageColor"
{
    Properties
    {
        _Surface ("Surface detail", Float) = 0
        _MainTex ("Surface atlas", 2D) = "white" {}
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        LOD 150

        CGPROGRAM
        #pragma target 3.0
        #pragma surface surf Lambert fullforwardshadows addshadow vertex:vert

        struct Input
        {
            fixed4 paint;
            float3 worldPos;
            float2 uv_MainTex;
        };

        void vert(inout appdata_full v, out Input output)
        {
            UNITY_INITIALIZE_OUTPUT(Input, output);
            output.paint = v.color;
        }

        float _Surface;
        sampler2D _MainTex;

        void surf(Input input, inout SurfaceOutput output)
        {
            float3 p = input.worldPos;
            float detail = 1;
            if (_Surface > 1.5)
            {
                float mottling = sin(31*p.x + 17*p.z + 11*p.y) * sin(25*p.z - 19*p.y);
                detail = .92 + .08*saturate(p.y) + .039*mottling * (1-saturate(length(fwidth(p))*13));
            }
            output.Albedo = input.paint.rgb * detail * tex2D(_MainTex, input.uv_MainTex).rgb;
            output.Alpha = 1;
        }
        ENDCG
    }
    FallBack "Diffuse"
}
