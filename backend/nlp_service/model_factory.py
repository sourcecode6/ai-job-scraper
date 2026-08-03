from sentence_transformers import SentenceTransformer

_model_instance = None

def get_sentence_transformer(model_name: str = 'sentence-transformers/all-MiniLM-L6-v2') -> SentenceTransformer:
    global _model_instance
    if _model_instance is None:
        print(f"Loading SentenceTransformer model '{model_name}'...")
        _model_instance = SentenceTransformer(model_name)
    return _model_instance
