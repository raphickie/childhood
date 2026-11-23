Shader "Childhood/MorningSky"
{
    SubShader
    {
        Tags { "Queue"="Background" "RenderType"="Background" "PreviewType"="Skybox" }
        Cull Off
        ZWrite Off

        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            struct Interpolators
            {
                float4 position : SV_POSITION;
                float3 direction : TEXCOORD0;
            };

            Interpolators vert(float4 vertex : POSITION)
            {
                Interpolators output;
                output.position = UnityObjectToClipPos(vertex);
                output.direction = vertex.xyz;
                return output;
            }

            fixed4 frag(Interpolators input) : SV_Target
            {
                float3 d = normalize(input.direction);
                float altitude = smoothstep(-.07, .72, d.y);
                float3 color = lerp(float3(.73, .80, .74), float3(.55, .70, .75), altitude);
                float towardSun = max(0., dot(d, normalize(float3(-.69, .58, -.43))));
                color += float3(.15, .10, .05) * pow(towardSun, 9.);
                color = lerp(color, float3(1., .93, .73), smoothstep(.99952, .99984, towardSun));
                #ifndef UNITY_COLORSPACE_GAMMA
                    color = GammaToLinearSpace(color);
                #endif
                return fixed4(color, 1.);
            }
            ENDCG
        }
    }
    FallBack Off
}
