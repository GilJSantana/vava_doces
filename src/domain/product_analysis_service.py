"""Servico para analise de produtos com integracao da receita, materia-prima e vendas.
Consolida dados das abas Receita, Materia Prima e Produtos para apresentacao no Streamlit.
"""

from __future__ import annotations

import logging
import re
from typing import Optional, TYPE_CHECKING

import pandas as pd

from src.ports.data_source import DataSource, DataSourceError

if TYPE_CHECKING:
    from src.infrastructure.gold_adapter import GoldParquetAdapter

logger = logging.getLogger(__name__)


class ProductAnalysisService:
    """Servico de custo/produto com caches e joins tolerantes a variacoes de schema."""

    _PROD_ID_CANDIDATES = [
        "id do produto", "productid", "product_id", "id produto", "idproduto",
        "prod id", "produto id",
    ]
    _PROD_NAME_CANDIDATES = [
        "nome do produto", "produto", "productname", "nome produto", "product name",
        "descricao", "descricao",
    ]
    _ING_ID_CANDIDATES = [
        "id_ingrediente", "id do ingrediente", "ingredienteid", "id ingrediente",
        "ingrediente id", "id_ing",
    ]
    _ING_NAME_CANDIDATES = [
        "ingrediente", "ingredientes", "ingredient", "nome ingrediente",
        "nome_ingrediente",
    ]
    _QTY_CANDIDATES = [
        "quantidade receita", "quantidade", "qtde", "qtd", "qtyperproduct",
        "qty", "quantidade por produto", "quant",
    ]
    _UNIT_CANDIDATES = [
        "unidade de medida", "unidade", "unit", "medida", "unid",
    ]
    _UNIT_COST_CANDIDATES = [
        "custo unitario", "custo unitario", "custo", "unit_price", "unit cost",
        "custo por unidade", "preco unitario", "preco unitario", "preco", "preco",
        "custo unitario mp (r$)", "custo unitario mp",
    ]

    SILVER_TAB_MAPPINGS = {
        "Materia Prima": {
            "item": ["id_ingrediente", "id do ingrediente", "ingrediente_id", "item", "id item"],
            "unidade": ["unidade", "unidade de medida", "unit", "unid"],
            "custo_unit": ["custo unitario", "custo unitario", "preco unitario", "preco unitario", "custo"],
        },
        "Receitas": {
            "produto_id": ["id do produto", "produto_id", "productid", "id produto"],
            "ingrediente_id": ["id do ingrediente", "id_ingrediente", "ingrediente_id", "ingredientid"],
            "qtd": ["quantidade receita", "quantidade", "qtd", "qtde", "qty"],
        },
        "Produtos": {
            "nome": ["nome do produto", "produto", "productname", "nome"],
            "rendimento": ["rendimento", "yield", "quantidade produzida"],
        },
    }

    def __init__(
        self,
        data_source: DataSource,
        gold_source: Optional["GoldParquetAdapter"] = None,
    ):
        self.data_source = data_source
        self.gold_source = gold_source
        self._cache_receita: Optional[pd.DataFrame] = None
        self._cache_materia_prima: Optional[pd.DataFrame] = None
        self._cache_produtos: Optional[pd.DataFrame] = None
        self._cache_vendas: Optional[pd.DataFrame] = None
        self._receita_loaded = False
        self._materia_prima_loaded = False
        self._produtos_loaded = False
        self._vendas_loaded = False

        self._cache_bom_breakdown: Optional[pd.DataFrame] = None
        self._bom_loaded = False
        self._cache_product_cost_summary: Optional[pd.DataFrame] = None

    # -------------------- helpers --------------------

    def _copy_df(self, df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
        return df.copy() if df is not None else None

    def _find_col(self, df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
        lower_map = {str(c).lower().strip(): c for c in df.columns}
        for cand in candidates:
            found = lower_map.get(cand.lower().strip())
            if found is not None:
                return found
        return None

    @staticmethod
    def _normalize_material_id(value) -> str:
        if value is None or pd.isna(value):
            return ""
        return str(value).strip().lower()

    def _clean_financial_column(self, series: pd.Series) -> pd.Series:
        as_text = series.astype(str).str.strip()
        as_text = as_text.str.replace("R$", "", regex=False).str.replace("$", "", regex=False)
        as_text = as_text.str.replace(" ", "", regex=False)
        as_text = as_text.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        cleaned = pd.to_numeric(as_text, errors="coerce")
        return pd.Series(cleaned, index=series.index)

    def _to_silver_materia_prima(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        mapping = self.SILVER_TAB_MAPPINGS["Materia Prima"]
        col_item = self._find_col(out, mapping["item"])
        col_unidade = self._find_col(out, mapping["unidade"])
        col_custo = self._find_col(out, mapping["custo_unit"])

        silver = pd.DataFrame(index=out.index)
        silver["item"] = out[col_item] if col_item else ""
        silver["unidade"] = out[col_unidade] if col_unidade else ""
        silver["custo_unit"] = self._clean_financial_column(out[col_custo]) if col_custo else pd.NA
        silver["item_norm"] = silver["item"].map(self._normalize_material_id)
        return silver

    def _to_silver_receitas(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        mapping = self.SILVER_TAB_MAPPINGS["Receitas"]
        col_prod = self._find_col(out, mapping["produto_id"])
        col_ing = self._find_col(out, mapping["ingrediente_id"])
        col_qtd = self._find_col(out, mapping["qtd"])

        silver = pd.DataFrame(index=out.index)
        silver["produto_id"] = out[col_prod] if col_prod else ""
        silver["ingrediente_id"] = out[col_ing] if col_ing else ""
        silver["qtd"] = pd.to_numeric(out[col_qtd], errors="coerce") if col_qtd else pd.NA
        silver["ingrediente_id_norm"] = silver["ingrediente_id"].map(self._normalize_material_id)
        return silver

    @staticmethod
    def _parse_float(value) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return None if pd.isna(value) else float(value)
        text = re.sub(r"[R$\s]", "", str(value).strip())
        if not text:
            return None
        if text.count(",") > 0 and text.count(".") > 0:
            text = text.replace(".", "")
        text = text.replace(",", ".")
        try:
            return float(text)
        except (ValueError, TypeError):
            return None

    def _load_first_sheet(self, sheet_names: list[str]) -> Optional[pd.DataFrame]:
        for name in sheet_names:
            try:
                df = self.data_source.get_data(name)
                if df is not None and not df.empty:
                    logger.debug("ProductAnalysisService: loaded sheet '%s' (%d rows)", name, len(df))
                    return df
            except (DataSourceError, KeyError, ValueError):
                continue
        return None

    # -------------------- loaders --------------------

    def _get_receita_data(self) -> Optional[pd.DataFrame]:
        if not self._receita_loaded:
            self._cache_receita = self._load_first_sheet(
                ["Receita", "Receitas", "BOM - Receitas", "BOM-Receitas", "Ficha Tecnica"]
            )
            self._receita_loaded = True
        return self._copy_df(self._cache_receita)

    def _get_materia_prima_data(self) -> Optional[pd.DataFrame]:
        if not self._materia_prima_loaded:
            self._cache_materia_prima = self._load_first_sheet(
                ["Materia Prima", "Matéria Prima", "Matria Prima", "Insumos", "Ingredientes"]
            )
            self._materia_prima_loaded = True
        return self._copy_df(self._cache_materia_prima)

    def _get_produtos_data(self) -> Optional[pd.DataFrame]:
        if not self._produtos_loaded:
            self._cache_produtos = self._load_first_sheet(
                ["Produtos", "Cadastro de Produtos", "Produto", "Receitas", "Produtos Finalizados"]
            )
            self._produtos_loaded = True
        return self._copy_df(self._cache_produtos)

    def _get_vendas_data(self) -> Optional[pd.DataFrame]:
        if not self._vendas_loaded:
            self._cache_vendas = self._load_first_sheet(
                ["Vendas Diarias", "Vendas Diárias", "Resumo Diario", "Resumo Diário", "Faturamento", "Vendas"]
            )
            self._vendas_loaded = True
        return self._copy_df(self._cache_vendas)

    # -------------------- BOM breakdown --------------------

    def _get_bom_breakdown(self) -> pd.DataFrame:
        if self._bom_loaded:
            cached = self._copy_df(self._cache_bom_breakdown)
            return cached if cached is not None else pd.DataFrame()

        self._bom_loaded = True

        receita = self._get_receita_data()
        if receita is None or receita.empty:
            logger.warning("ProductAnalysisService: aba Receita nao encontrada ou vazia.")
            self._cache_bom_breakdown = pd.DataFrame()
            return pd.DataFrame()

        rec = receita.copy()
        silver_rec = self._to_silver_receitas(rec)

        prod_id_col = self._find_col(rec, self._PROD_ID_CANDIDATES)
        prod_name_col = self._find_col(rec, self._PROD_NAME_CANDIDATES)
        ing_id_col = self._find_col(rec, self._ING_ID_CANDIDATES)
        ing_name_col = self._find_col(rec, self._ING_NAME_CANDIDATES)
        qty_col = self._find_col(rec, self._QTY_CANDIDATES)
        unit_col = self._find_col(rec, self._UNIT_CANDIDATES)
        unit_cost_rec = self._find_col(rec, self._UNIT_COST_CANDIDATES)

        if not prod_id_col and not prod_name_col:
            logger.warning("ProductAnalysisService: colunas de produto nao encontradas na aba Receita.")
            self._cache_bom_breakdown = pd.DataFrame()
            return pd.DataFrame()

        mp_cost_map: dict[str, Optional[float]] = {}
        mp_unit_map: dict[str, str] = {}
        mp_name_map: dict[str, str] = {}

        materia = self._get_materia_prima_data()
        if materia is not None and not materia.empty:
            silver_mp = self._to_silver_materia_prima(materia)
            mp_name_c = self._find_col(materia, self._ING_NAME_CANDIDATES)
            for idx, row in silver_mp.iterrows():
                key = row.get("item_norm", "")
                if not key:
                    continue
                mp_cost_map[key] = row.get("custo_unit")
                if pd.notna(row.get("unidade")):
                    mp_unit_map[key] = str(row["unidade"]).strip()
                if mp_name_c and idx in materia.index and pd.notna(materia.loc[idx, mp_name_c]):
                    mp_name_map[key] = str(materia.loc[idx, mp_name_c]).strip()

        produto_name_map: dict[str, str] = {}
        produtos = self._get_produtos_data()
        if produtos is not None and not produtos.empty:
            p_id_c = self._find_col(produtos, self._PROD_ID_CANDIDATES)
            p_name_c = self._find_col(produtos, self._PROD_NAME_CANDIDATES)
            if p_id_c and p_name_c:
                for _, row in produtos.iterrows():
                    if pd.notna(row.get(p_id_c)):
                        produto_name_map[str(row[p_id_c]).strip()] = str(row[p_name_c]).strip()

        rows = []
        for idx, row in rec.iterrows():
            prod_id = str(row[prod_id_col]).strip().upper() if prod_id_col and pd.notna(row.get(prod_id_col)) else ""
            if not prod_id and prod_name_col and pd.notna(row.get(prod_name_col)):
                prod_id = str(row[prod_name_col]).strip().upper()
            if not prod_id:
                continue

            prod_name = ""
            if prod_name_col and pd.notna(row.get(prod_name_col)):
                prod_name = str(row[prod_name_col]).strip()
            if not prod_name:
                prod_name = produto_name_map.get(prod_id, prod_id)

            ing_id_raw = str(row[ing_id_col]).strip() if ing_id_col and pd.notna(row.get(ing_id_col)) else ""
            ing_id = ing_id_raw
            ing_key = self._normalize_material_id(ing_id_raw)
            if idx in silver_rec.index:
                norm_from_silver = silver_rec.at[idx, "ingrediente_id_norm"]
                if isinstance(norm_from_silver, str) and norm_from_silver.strip() != "":
                    ing_key = norm_from_silver

            ing_name = ""
            if ing_name_col and pd.notna(row.get(ing_name_col)):
                ing_name = str(row[ing_name_col]).strip()
            if not ing_name and ing_id:
                ing_name = mp_name_map.get(ing_key, ing_id)

            qty = self._parse_float(row[qty_col]) if qty_col and pd.notna(row.get(qty_col)) else None

            unit = ""
            if unit_col and pd.notna(row.get(unit_col)):
                unit = str(row[unit_col]).strip()
            if not unit and ing_id:
                unit = mp_unit_map.get(ing_key, "")

            unit_cost: Optional[float] = None
            origem = "N/A"
            if unit_cost_rec and pd.notna(row.get(unit_cost_rec)):
                unit_cost = self._parse_float(row[unit_cost_rec])
                if unit_cost is not None:
                    origem = "Receita"
            if unit_cost is None and ing_key and ing_key in mp_cost_map:
                unit_cost = mp_cost_map[ing_key]
                if unit_cost is not None:
                    origem = "Materia Prima"

            ing_cost = (qty * unit_cost) if (qty is not None and unit_cost is not None) else None

            rows.append(
                {
                    "ID do Produto": prod_id,
                    "Produto": prod_name,
                    "ID do Ingrediente": ing_id,
                    "Ingrediente": ing_name,
                    "Quantidade Receita": qty,
                    "Unidade de Medida": unit,
                    "Custo Unitario MP (R$)": unit_cost,
                    "Custo do Ingrediente (R$)": ing_cost,
                    "Custo da Receita (R$)": None,
                    "Origem do Custo": origem,
                }
            )

        if not rows:
            self._cache_bom_breakdown = pd.DataFrame()
            return pd.DataFrame()

        bom_df = pd.DataFrame(rows)
        self._cache_bom_breakdown = bom_df
        logger.info(
            "ProductAnalysisService: BOM breakdown built - %d rows, %d produtos",
            len(bom_df),
            bom_df["ID do Produto"].nunique(),
        )
        return bom_df.copy()

    # -------------------- public API --------------------

    def get_product_cost_breakdown(self) -> pd.DataFrame:
        return self._get_bom_breakdown()

    def get_recipe_cost_issues(self) -> pd.DataFrame:
        bom = self._get_bom_breakdown()
        if bom.empty:
            return pd.DataFrame()
        issues = bom[bom["Custo do Ingrediente (R$)"].isna()].copy()
        return issues.reset_index(drop=True)

    def get_product_cost_summary(self) -> pd.DataFrame:
        if self._cache_product_cost_summary is not None:
            return self._cache_product_cost_summary.copy()

        bom = self._get_bom_breakdown()
        if not bom.empty:
            grp = bom.groupby(["ID do Produto", "Produto"], as_index=False)
            bom_agg = pd.DataFrame(grp.agg(**{"Qtd Ingredientes": ("Ingrediente", "count")}))
            cost_sum = (
                bom.groupby(["ID do Produto", "Produto"])["Custo do Ingrediente (R$)"]
                .apply(lambda s: float(s.dropna().sum()) if s.notna().any() else None)
                .reset_index()
                .rename(columns={"Custo do Ingrediente (R$)": "Custo Total (R$)"})
            )
            bom_agg = bom_agg.merge(cost_sum, on=["ID do Produto", "Produto"], how="left")
        else:
            bom_agg = pd.DataFrame(columns=["ID do Produto", "Produto", "Qtd Ingredientes", "Custo Total (R$)"])

        registered = self.get_registered_products()
        if not registered.empty:
            base_cols = ["ID do Produto"]
            prod_name_col = "Nome do Produto" if "Nome do Produto" in registered.columns else None
            if prod_name_col:
                base_cols.append(prod_name_col)
            base = registered[base_cols].drop_duplicates(subset=["ID do Produto"]).copy()
            if prod_name_col:
                base = base.rename(columns={prod_name_col: "Produto"})
            if "Produto" not in base.columns:
                base["Produto"] = base["ID do Produto"]
            summary = base.merge(
                bom_agg[["ID do Produto", "Qtd Ingredientes", "Custo Total (R$)"]],
                on="ID do Produto",
                how="left",
            )
            summary["Qtd Ingredientes"] = summary["Qtd Ingredientes"].fillna(0).astype(int)
        else:
            summary = bom_agg

        summary = summary.sort_values("ID do Produto").reset_index(drop=True)
        self._cache_product_cost_summary = summary
        return summary.copy()

    def get_registered_products(self) -> pd.DataFrame:
        produtos = self._get_produtos_data()
        if produtos is None or produtos.empty:
            return pd.DataFrame(columns=["ID do Produto", "Nome do Produto"])

        df = produtos.copy()
        id_col = self._find_col(df, self._PROD_ID_CANDIDATES)
        if id_col is None and "" in df.columns:
            id_col = ""
        if id_col is None:
            return pd.DataFrame(columns=["ID do Produto", "Nome do Produto"])

        if id_col != "ID do Produto":
            df = df.rename(columns={id_col: "ID do Produto"})

        df["ID do Produto"] = df["ID do Produto"].astype(str).str.strip().str.upper()
        df = df[df["ID do Produto"].ne("") & df["ID do Produto"].ne("NAN")].copy()

        name_col = self._find_col(df, self._PROD_NAME_CANDIDATES)
        if name_col and name_col != "Nome do Produto":
            df = df.rename(columns={name_col: "Nome do Produto"})
        elif "Nome do Produto" not in df.columns:
            df["Nome do Produto"] = df["ID do Produto"]

        return df.reset_index(drop=True)

    def get_products_with_sales_impact(self) -> pd.DataFrame:
        summary = self.get_product_cost_summary()
        if summary.empty:
            return pd.DataFrame()

        produtos = self._get_produtos_data()
        if produtos is not None and not produtos.empty:
            p_id_col = self._find_col(produtos, self._PROD_ID_CANDIDATES)
            price_col = self._find_col(
                produtos,
                [
                    "preco de venda", "preco de venda (r$)", "preco", "price", "valor de venda",
                    "preço de venda", "preço", "valor venda",
                ],
            )
            if p_id_col and price_col:
                price_df = produtos[[p_id_col, price_col]].copy()
                price_df[p_id_col] = price_df[p_id_col].astype(str).str.strip().str.upper()
                price_df = price_df[price_df[p_id_col].ne("")]
                price_df["_price"] = price_df[price_col].apply(self._parse_float)
                price_df = price_df.rename(columns={p_id_col: "ID do Produto"})
                summary = summary.merge(price_df[["ID do Produto", "_price"]], on="ID do Produto", how="left")
                summary["Preco de Venda (R$)"] = summary["_price"]
                summary = summary.drop(columns=["_price"])

                def _margin(row) -> Optional[float]:
                    price = row.get("Preco de Venda (R$)")
                    cost = row.get("Custo Total (R$)")
                    if pd.notna(price) and price > 0 and pd.notna(cost):
                        return (price - cost) / price * 100
                    return None

                summary["Margem (%)"] = summary.apply(_margin, axis=1)

        result = summary[summary["Custo Total (R$)"].notna()].copy()
        return result.reset_index(drop=True)

    def get_product_profitability_analysis(self) -> pd.DataFrame:
        registered = self.get_registered_products()
        if registered.empty:
            return pd.DataFrame()

        cost_summary = self.get_product_cost_summary()
        if not cost_summary.empty and "Custo Total (R$)" in cost_summary.columns:
            base = registered.merge(
                cost_summary[["ID do Produto", "Custo Total (R$)"]],
                on="ID do Produto",
                how="left",
            )
        else:
            base = registered.copy()
            base["Custo Total (R$)"] = None

        base["Custo Real"] = base["Custo Total (R$)"].fillna(0.0)

        produtos = self._get_produtos_data()
        if produtos is not None and not produtos.empty:
            p_id_col = self._find_col(produtos, self._PROD_ID_CANDIDATES)
            price_col = self._find_col(produtos, ["preco de venda", "preço de venda", "preco", "preço", "price"])
            if p_id_col and price_col:
                prc = produtos[[p_id_col, price_col]].copy()
                prc[p_id_col] = prc[p_id_col].astype(str).str.strip().str.upper()
                prc["_price"] = prc[price_col].apply(self._parse_float)
                prc = prc.rename(columns={p_id_col: "ID do Produto"})
                base = base.merge(prc[["ID do Produto", "_price"]], on="ID do Produto", how="left")
                base["Preco de Venda (R$)"] = base["_price"]
                base = base.drop(columns=["_price"])

        vendas = self._get_vendas_data()
        if vendas is None or vendas.empty:
            return pd.DataFrame()

        v = vendas.copy()
        v_id_col = self._find_col(v, self._PROD_ID_CANDIDATES)
        v_name_col = self._find_col(v, self._PROD_NAME_CANDIDATES)
        v_qty_col = self._find_col(v, ["quantidade vendida", "qtd vendida", "volume", "quantidade", "qtd"])
        v_fat_col = self._find_col(v, ["faturamento total", "faturamento", "receita", "valor total", "total", "receita total"])

        if v_qty_col:
            v["Volume de Vendas"] = pd.to_numeric(v[v_qty_col], errors="coerce")
        if v_fat_col:
            v["Faturamento Total"] = v[v_fat_col].apply(self._parse_float)

        if v_id_col:
            v[v_id_col] = v[v_id_col].astype(str).str.strip().str.upper()
            v_merge = v.rename(columns={v_id_col: "ID do Produto"})
            cols = ["ID do Produto"] + (["Volume de Vendas"] if "Volume de Vendas" in v_merge.columns else []) + (["Faturamento Total"] if "Faturamento Total" in v_merge.columns else [])
            result = base.merge(v_merge[cols], on="ID do Produto", how="inner")
        elif v_name_col and "Nome do Produto" in base.columns:
            v_merge = v.rename(columns={v_name_col: "Nome do Produto"})
            cols = ["Nome do Produto"] + (["Volume de Vendas"] if "Volume de Vendas" in v_merge.columns else []) + (["Faturamento Total"] if "Faturamento Total" in v_merge.columns else [])
            result = base.merge(v_merge[cols], on="Nome do Produto", how="inner")
        else:
            return pd.DataFrame()

        if "Preco de Venda (R$)" in result.columns:
            result["Margem de Contribuicao (R$)"] = result.apply(
                lambda r: (r["Preco de Venda (R$)"] - r["Custo Real"]) if pd.notna(r.get("Preco de Venda (R$)")) else None,
                axis=1,
            )
            result["Margem de Contribuicao (%)"] = result.apply(
                lambda r: (r["Margem de Contribuicao (R$)"] / r["Preco de Venda (R$)"] * 100)
                if pd.notna(r.get("Margem de Contribuicao (R$)")) and r.get("Preco de Venda (R$)", 0) > 0
                else None,
                axis=1,
            )

        return result.reset_index(drop=True)

    def get_sales_data(self, prefer_gold: bool = False) -> Optional[pd.DataFrame]:
        if prefer_gold and self.gold_source is not None:
            try:
                return self.gold_source.load_gold("fato_vendas")
            except Exception:
                pass
        return self._get_vendas_data()

    def get_receita_data(self) -> Optional[pd.DataFrame]:
        return self._get_receita_data()

    def get_materia_prima_data(self) -> Optional[pd.DataFrame]:
        return self._get_materia_prima_data()

    def get_produtos_data(self) -> Optional[pd.DataFrame]:
        return self._get_produtos_data()
