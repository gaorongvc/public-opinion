from openai import OpenAI

client = OpenAI(api_key="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",
                base_url='https://proxy.oldlau.com/openai/v1')
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import PointStruct

# from sentence_transformers import SentenceTransformer


embedding_model = "text-embedding-ada-002"

# encoder = SentenceTransformer("all-MiniLM-L6-v2")

qdrant = QdrantClient(url="https://a1eab2ee-10e1-49e6-b18f-2e0710a6e377.us-east4-0.gcp.cloud.qdrant.io:6333",
                      api_key="0yPNxdoxPHvSDaN4R7FYy-_-OPBVYgfb_93bm1G-SQ_F-Tv7Ozc4Cg")


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
