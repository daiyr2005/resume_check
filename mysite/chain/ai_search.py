from langchain_community.document_loaders import TextLoader
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

document = TextLoader('mysite/chain/base/data.txt', encoding='utf-8').load()
chunks = RecursiveCharacterTextSplitter(
    chunk_size=600,
    chunk_overlap=100
).split_documents(document)

embeddings = OllamaEmbeddings(model='nomic-embed-text')
vector_store = InMemoryVectorStore.from_documents(chunks, embeddings)

prompt = ChatPromptTemplate.from_messages(
    [
        (
            'system',
            'Ты HR-ассистент, который проверяет резюме. '
            'Сравни навыки из резюме с требованиями из Базы Знаний: '
            '"База знаний: {base_knowledge}". '
            'Опирайся только на текст резюме и Базу Знаний. '
            'Не придумывай навыки, которых нет в резюме. '
            'Если навыки подходят под требования, '
            'первой строкой напиши: "Вердикт: подходит". '
            'Если не подходят, первой строкой напиши: "Вердикт: не подходит". '
            'Дальше коротко, на русском: найденные навыки и чего не хватает.'
        ),
        ('human', 'Резюме кандидата: {content}')
    ]
)

model = ChatOllama(model='llama3.2:latest', temperature=0)
chain = prompt | model | StrOutputParser()