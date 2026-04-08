"""Componentes e utilitários de renderização Streamlit."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import streamlit as st
from pandas.io.formats.style import Styler

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def profile_data_by_layer(
    bronze_path: Path = Path("data/processed/silver/sales_silver.parquet"),
    gold_dir: Path = Path("data/processed/gold"),
) -> dict[str, dict[str, int]]:
    """Generate data profile: record counts by month across all layers.

    Returns:
        {"bronze": {...}, "gold_fato": {...}, "gold_dim_tempo": {...}}
    """
    # Bronze: count by mes_referencia
    bronze_counts = {}
    if bronze_path.exists():
        try:
            df = pd.read_parquet(bronze_path)
            if "mes_referencia" in df.columns:
                bronze_counts = (
                    df["mes_referencia"]
                    .fillna("unknown")
                    .astype(str)
                    .value_counts()
                    .sort_index()
                    .to_dict()
                )
        except Exception as exc:
            logger.warning("profile_data_by_layer:bronze: %s", exc)

    # Gold fato: count by month (data_id -> dim_tempo)
    fato_counts = {}
    fato_path = gold_dir / "fato_vendas.parquet"
    dim_tempo_path = gold_dir / "dim_tempo.parquet"
    if fato_path.exists() and dim_tempo_path.exists():
        try:
            fato = pd.read_parquet(fato_path)
            dim_tempo = pd.read_parquet(dim_tempo_path)
            merged = fato.merge(dim_tempo[["data_id", "data"]], on="data_id", how="left")
            merged["mes"] = pd.to_datetime(merged.get("data"), errors="coerce").dt.to_period("M").astype(str)
            fato_counts = (
                merged["mes"]
                .fillna("unknown")
                .astype(str)
                .value_counts()
                .sort_index()
                .to_dict()
            )
        except Exception as exc:
            logger.warning("profile_data_by_layer:fato: %s", exc)

    # Dim tempo: cardinality of dates by month
    tempo_counts = {}
    if dim_tempo_path.exists():
        try:
            dim_tempo = pd.read_parquet(dim_tempo_path)
            if "data" in dim_tempo.columns:
                dim_tempo["mes"] = pd.to_datetime(dim_tempo["data"], errors="coerce").dt.to_period("M").astype(str)
                tempo_counts = (
                    dim_tempo["mes"]
                    .fillna("unknown")
                    .astype(str)
                    .value_counts()
                    .sort_index()
                    .to_dict()
                )
        except Exception as exc:
            logger.warning("profile_data_by_layer:tempo: %s", exc)

    return {
        "bronze": bronze_counts,
        "gold_fato": fato_counts,
        "gold_dim_tempo": tempo_counts,
    }


def format_profile_for_display(profile: dict[str, dict[str, int]]) -> pd.DataFrame:
    """Convert profile dict to DataFrame for display in Streamlit."""
    bronze = profile.get("bronze", {})
    gold_fato = profile.get("gold_fato", {})
    gold_dim_tempo = profile.get("gold_dim_tempo", {})

    all_months = sorted(set(bronze.keys()) | set(gold_fato.keys()) | set(gold_dim_tempo.keys()))

    rows = []
    for month in all_months:
        bronze_count = bronze.get(month, 0)
        fato_count = gold_fato.get(month, 0)
        tempo_count = gold_dim_tempo.get(month, 0)
        delta = bronze_count - fato_count

        rows.append(
            {
                "Mês": month,
                "Bronze (Silver)": bronze_count,
                "Gold Fato": fato_count,
                "Dim Tempo": tempo_count,
                "Δ (Bronze → Fato)": delta,
                "Status": "✅" if delta == 0 else f"⚠️ -{delta}" if delta > 0 else f"⚠️ +{abs(delta)}",
            }
        )

    return pd.DataFrame(rows)


def render_separator() -> None:
    """Renderiza separador visual padrão."""
    st.markdown("---")


def render_wrapped_dataframe(
    df: pd.DataFrame | Styler,
    column_config: dict | None = None,
) -> None:
    """Renderiza dataframe em wrapper visual padronizado."""
    st.markdown('<div class="dataframe-wrapper">', unsafe_allow_html=True)
    st.dataframe(df, width="stretch", hide_index=True, column_config=column_config)
    st.markdown('</div>', unsafe_allow_html=True)


def build_product_label(row: pd.Series, id_col: str, name_col: str) -> str:
    """Monta label padrão para exibição de produto."""
    return f"{row[id_col]} - {row[name_col]}"


def build_product_labels(df: pd.DataFrame, id_col: str, name_col: str) -> pd.Series:
    """Monta labels de produto de forma vetorizada para melhor performance."""
    return (
        df[id_col].fillna("").astype(str).str.strip()
        + " - "
        + df[name_col].fillna("").astype(str).str.strip()
    )


def render_metric_card(col, title: str, value: str, caption: str | None = None) -> None:
    """Renderiza card de métrica com estilo padrão."""
    with col:
        st.markdown(
            f"<div class='metric-card'><div class='card-title'>{title}</div><div class='card-value'>{value}</div></div>",
            unsafe_allow_html=True,
        )
        if caption:
            st.caption(caption)


def render_app_header(
    title: str = "🍰 Vava Doces - Análise de Produtos e Vendas",
    subtitle: str = "_Ferramenta de análise de produtos, custos e vendas_",
    logo_path: str = "assets/logo.png",
) -> None:
    """Renderiza cabeçalho principal com logotipo, título e subtítulo."""
    resolved_logo_path = PROJECT_ROOT / logo_path
    st.markdown('<div class="header">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        try:
            st.markdown('<div class="vava-logo-wrapper">', unsafe_allow_html=True)
            if resolved_logo_path.exists():
                st.image(str(resolved_logo_path), width=150)
            else:
                raise FileNotFoundError(str(resolved_logo_path))
            st.markdown('</div>', unsafe_allow_html=True)
        except Exception:
            st.markdown('<div class="vava-logo-wrapper">', unsafe_allow_html=True)
            st.markdown(
                '<div style="width:150px;height:150px;border-radius:999px;background:#C9A23A;display:inline-block"></div>',
                unsafe_allow_html=True,
            )
            st.markdown('</div>', unsafe_allow_html=True)

    st.title(title)
    st.markdown(subtitle)
    st.markdown('</div>', unsafe_allow_html=True)

