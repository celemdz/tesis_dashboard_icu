import streamlit.components.v1 as components

import streamlit as st

fr_resp = 20.0 
tiempo_ciclo = 60 / fr_resp 

svg_pulmones = f"""
<div style="display: flex; justify-content: center; align-items: center; background-color: #1C1E24; padding: 20px; border-radius: 10px;">
    <svg width="200" height="200" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
        <!-- Tráquea -->
        <line x1="48" y1="5" x2="48" y2="25" stroke="#a4b0be" stroke-width="1.5" stroke-dasharray="2,2" />
        <line x1="52" y1="5" x2="52" y2="25" stroke="#a4b0be" stroke-width="1.5" stroke-dasharray="2,2" />
        
        <!-- Pulmones con animación nativa -->
        <g style="transform-origin: 50px 60px;">
            <animateTransform attributeName="transform" type="scale" values="0.95; 1.08; 0.95" dur="{tiempo_ciclo}s" repeatCount="indefinite" />
            <path d="M 45,25 C 25,15 10,35 15,65 C 20,90 40,95 45,95 C 45,95 48,70 45,25 Z" fill="rgba(0, 176, 255, 0.15)" stroke="#00B0FF" stroke-width="2.5" />
            <path d="M 55,25 C 75,15 90,35 85,65 C 80,90 60,95 55,95 C 55,95 52,70 55,25 Z" fill="rgba(0, 176, 255, 0.15)" stroke="#00B0FF" stroke-width="2.5" />
        </g>
    </svg>
</div>
"""

components.html(svg_pulmones, height=250)