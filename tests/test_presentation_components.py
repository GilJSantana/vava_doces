import pandas as pd

from src.presentation.components import build_product_label, build_product_labels


def test_build_product_label_with_valid_fields():
    row = pd.Series({"ID do Produto": "PROD-001", "Produto": "Brigadeiro"})

    label = build_product_label(row, "ID do Produto", "Produto")

    assert label == "PROD-001 - Brigadeiro"


def test_build_product_label_with_name_column_variation():
    row = pd.Series({"ID do Produto": "PROD-002", "Nome do Produto": "Beijinho"})

    label = build_product_label(row, "ID do Produto", "Nome do Produto")

    assert label == "PROD-002 - Beijinho"


def test_build_product_labels_vectorized():
    df = pd.DataFrame(
        {
            "ID do Produto": ["PROD-001", "PROD-002"],
            "Produto": ["Brigadeiro", "Beijinho"],
        }
    )

    labels = build_product_labels(df, "ID do Produto", "Produto")

    assert labels.tolist() == ["PROD-001 - Brigadeiro", "PROD-002 - Beijinho"]


