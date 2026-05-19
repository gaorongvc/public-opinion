import os

from openai import OpenAI
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import PointStruct

# from sentence_transformers import SentenceTransformer

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL", "https://proxy.oldlau.com/openai/v1"))

embedding_model = "text-embedding-ada-002"

# encoder = SentenceTransformer("all-MiniLM-L6-v2")

qdrant = QdrantClient(url=os.getenv("QDRANT_URL"),
                      api_key=os.getenv("QDRANT_API_KEY"))


def embed(_id, text):
    response = client.embeddings.create(input=[text], model=embedding_model)
    embedding = response.data[0].embedding
    print(embedding)
    info = qdrant.upsert(
        collection_name="wechat_article",
        wait=True,
        points=[PointStruct(id=_id, vector=embedding, payload={"summary": text})],
    )
    print(info)
    return embedding


def search(text):
    response = client.embeddings.create(input=[text], model=embedding_model)
    embedding = response.data[0].embedding
    hits = qdrant.search(
        collection_name="wechat_article",
        query_vector=embedding,
        limit=3,
    )
    print(hits)


def init():
    qdrant.recreate_collection(
        collection_name="wechat_article",
        vectors_config=models.VectorParams(
            size=1536,
            distance=models.Distance.COSINE,
        ),
    )


if __name__ == '__main__':
    # init()
    # embed('AA74F9E2143FF00C693FC4DB523F2CE7',
    #       'AI扩图技术因其出人意料的效果在网友中引发热议，尽管有时结果离谱，但也为人们带来乐趣。')
    search('AI扩图技术因其出人意料的效果在网友中引发热议，尽管有时结果离谱，但也为人们带来乐趣。')
