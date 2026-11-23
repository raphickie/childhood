Shader "Childhood/CarGlass"
{
    SubShader
    {
        Tags { "Queue"="Transparent" "RenderType"="Transparent" }
        Cull Off
        ZWrite Off
        Blend SrcAlpha OneMinusSrcAlpha
        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            struct Varyings
            {
                float4 position : SV_POSITION;
                float3 world : TEXCOORD0;
                float3 normal : TEXCOORD1;
                fixed3 tint : COLOR0;
            };

            Varyings vert(appdata_full v)
            {
                Varyings output;
                output.position = UnityObjectToClipPos(v.vertex);
                output.world = mul(unity_ObjectToWorld, v.vertex).xyz;
                output.normal = UnityObjectToWorldNormal(v.normal);
                output.tint = v.color.rgb;
                return output;
            }

            fixed4 frag(Varyings i) : SV_Target
            {
                float3 view = normalize(_WorldSpaceCameraPos - i.world);
                float fresnel = pow(1.0 - saturate(abs(dot(normalize(i.normal), view))), 3.0);
                return fixed4(i.tint * (.84 + .16 * fresnel), .18 + .24 * fresnel);
            }
            ENDCG
        }
    }
}
