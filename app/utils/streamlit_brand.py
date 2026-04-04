# -*- coding: utf-8 -*-
"""브랜드 로고 표시 — `st.image`는 좁은 열/특정 버전에서 width=0 오류가 나므로 HTML img 사용."""
from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st


def render_logo_png(logo_path: Path, *, width_px: int = 92) -> None:
    if not logo_path.is_file():
        return
    try:
        raw = logo_path.read_bytes()
    except OSError:
        return
    if not raw:
        return
    b64 = base64.b64encode(raw).decode("ascii")
    st.markdown(
        f'<img src="data:image/png;base64,{b64}" alt="" '
        f'width="{width_px}" '
        f'style="width:{width_px}px;max-width:100%;height:auto;display:block;'
        f'object-fit:contain;" />',
        unsafe_allow_html=True,
    )
