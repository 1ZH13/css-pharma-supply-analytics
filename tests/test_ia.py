"""Pruebas de la Etapa 3 sin conexión: Gemini se reemplaza por un cliente simulado."""
import pandas as pd

import pipeline.ia_texto as T
from pipeline.ia import candidatos

CATALOGO = pd.DataFrame({
    "codigo": ["101000801", "101030001", "102050001", "102050002"],
    "descripcion": ["GLIBENCLAMIDA, 5MG, TABLETA", "AMLODIPINA 5mg, tableta", "INSULINA NPH 100 UI/mL",
                    "INSULINA GLARGINA 100 UI/mL"],
    "principio_activo": ["GLIBENCLAMIDA", "AMLODIPINA", "INSULINA NPH", "INSULINA GLARGINA"],
})


def test_menciones_se_enlazan_con_el_catalogo():
    analisis = [{"id": "n01", "tipo_evento": "desabastecimiento", "riesgo": "alto",
                 "medicamentos": [{"nombre": "insulina", "principio_activo": "Insulina", "situacion": "faltante"},
                                  {"nombre": "amlodipino", "principio_activo": "AMLODIPINA", "situacion": "en_compra"},
                                  {"nombre": "x", "principio_activo": "MEDICAMENTO INEXISTENTE", "situacion": "faltante"}]}]
    m = T.menciones(analisis, CATALOGO)
    assert set(m.loc[m["principio_activo_mencion"] == "INSULINA", "codigo"]) == {"102050001", "102050002"}
    assert m.loc[m["principio_activo_mencion"] == "AMLODIPINA", "coincidencia"].iloc[0] == "exacta"
    assert m.loc[m["principio_activo_mencion"] == "MEDICAMENTO INEXISTENTE", "codigo"].isna().all()


def test_cruce_fda_por_nombre_en_ingles():
    inn = pd.DataFrame({"principio_activo": ["GLIBENCLAMIDA", "AMLODIPINA"], "inn_en": ["glyburide", "amlodipine"]})
    fda = pd.DataFrame({"sustancia": ["GLYBURIDE", "AMLODIPINE BESYLATE"], "generic_name": ["Glyburide Tablets", "Amlodipine"],
                        "status": ["Current", "Resolved"], "motivo": ["Demand increase", None],
                        "fecha_actualizacion": ["2026-11-01", "2025-01-01"]})
    c = T.cruce_fda(CATALOGO, inn, fda).set_index("codigo")
    assert bool(c.loc["101000801", "escasez_eeuu_vigente"]) is True
    assert bool(c.loc["101030001", "escasez_eeuu_vigente"]) is False


def test_seleccion_de_modelo_prefiere_flash_estable_mas_reciente(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    c = candidatos(["gemini-2.5-flash", "gemini-3.6-flash", "gemini-3.6-flash-image", "gemini-flash-latest", "gemini-3-pro"])
    assert c[0] == "gemini-3.6-flash" and "gemini-3.6-flash-image" not in c and "gemini-3-pro" not in c


def test_timeout_pasa_al_siguiente_modelo(monkeypatch):
    import requests
    import pipeline.ia as ia
    llamadas = []

    def falso_post(url, **kw):
        llamadas.append(url)
        if "gemini-3.8-flash" in url:
            raise requests.ReadTimeout("lento")
        class R:
            status_code = 200
            @staticmethod
            def json():
                return {"candidates": [{"content": {"parts": [{"text": '{"estado": "ok"}'}]}}]}
        return R()

    monkeypatch.setattr(ia.requests, "post", falso_post)
    monkeypatch.setattr(ia.time, "sleep", lambda s: None)
    monkeypatch.setattr(ia, "modelos", lambda clave=None: ["gemini-3.8-flash", "gemini-3.6-flash"])
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    cli = ia.ClienteGemini(pausa=0)
    assert cli.json("hola", {"type": "OBJECT"}) == {"estado": "ok"}
    assert cli.modelo == "gemini-3.6-flash"


def test_publicar_no_incluye_textos_de_terceros(tmp_path):
    import json
    from pipeline.publicar import publicar
    origen, destino = tmp_path / "o", tmp_path / "d"
    origen.mkdir(); destino.mkdir()
    (origen / "documentos.jsonl").write_text(json.dumps({"id": "n01", "url": "u", "texto": "cuerpo completo"}) + "\n", encoding="utf-8")
    (origen / "ia_documentos.jsonl").write_text(json.dumps({"id": "n01", "resumen": "r"}) + "\n", encoding="utf-8")
    (destino / "viejo.csv").write_text("x", encoding="utf-8")
    publicar(origen, destino)
    doc = json.loads((destino / "documentos.jsonl").read_text(encoding="utf-8"))
    assert "texto" not in doc and doc["url"] == "u"
    assert (destino / "ia_documentos.jsonl").exists() and not (destino / "viejo.csv").exists()


def test_asistente_cambia_de_modelo_si_se_agota_la_cuota(monkeypatch):
    import pipeline.ia as ia
    monkeypatch.setattr(ia, "_clave", lambda: "x")
    monkeypatch.setattr(ia, "modelos", lambda c=None: ["gemini-9.0-flash", "gemini-8.0-flash"])
    usados = []

    def generar(prompt, *, modelo, **k):
        usados.append(modelo)
        if modelo == "gemini-9.0-flash":
            raise ia.ErrorIA("Se alcanzó el límite de uso de la capa gratuita (RESOURCE_EXHAUSTED).")
        return "ok"

    monkeypatch.setattr(ia, "generar", generar)
    cli = ia.ClienteGemini(pausa=0, timeout=30, reintentos=1, max_modelos=4)
    assert cli.texto("hola") == "ok"
    assert usados == ["gemini-9.0-flash", "gemini-8.0-flash"]


def test_proveedor_alterno_prefiere_modelos_de_chat_grandes():
    from pipeline.ia import candidatos_alternos
    c = candidatos_alternos(["whisper-large-v3", "llama-3.1-8b-instant", "llama-3.3-70b-versatile",
                             "meta-llama/llama-guard-4-12b", "openai/gpt-oss-120b"])
    assert c[0] == "llama-3.3-70b-versatile"
    assert "whisper-large-v3" not in c and not any("guard" in m for m in c)


def test_respaldo_pasa_al_segundo_proveedor_si_el_primero_falla():
    from pipeline.ia import ClienteConRespaldo, ErrorIA

    class Falla:
        modelo = "gemini-x"
        def texto(self, *a, **k):
            raise ErrorIA("429 límite de uso")

    class Ok:
        modelo = "Groq · llama"
        def texto(self, *a, **k):
            return "respuesta"

    c = ClienteConRespaldo([Falla(), Ok()])
    assert c.texto("hola") == "respuesta" and c.modelo == "Groq · llama"
