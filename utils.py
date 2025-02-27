# utils.py
from transformers import pipeline
from datasets import Dataset
from ebooklib import epub
from ebooklib import ITEM_DOCUMENT
import PyPDF2
from bs4 import BeautifulSoup
import docx
import re
from collections import Counter
from langdetect import detect
from sklearn.feature_extraction.text import TfidfVectorizer
import unicodedata
import numpy as np
import spacy
import torch
import sys
import logging
import os
from werkzeug.datastructures import FileStorage

os.environ['CUDA_LAUNCH_BLOCKING'] = '1'  # 동기화된 디버깅 활성화

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 지원되는 언어 및 모델 매핑
supported_languages = {
    "en": "facebook/bart-large-cnn",  # 영어
    "ko": "ainize/kobart-news",  # 한국어
    "zh": "csebuetnlp/mT5_multilingual_XLSum",  # 중국어
    "es": "csebuetnlp/mT5_multilingual_XLSum",  # 스페인어
    "it": "gsarti/it5-small",  # 이탈리아어
    "ja": "sonoisa/t5-base-japanese",  # 일본어
    "de": "ml6team/mt5-small-german-finetune-sum-de",  # 독일어
    "fr": "plguillou/t5-base-fr-sum-cnndm",  # 프랑스어
}

def preprocess_text(text):
    """
    텍스트를 전처리합니다.
    """
    if not text.strip():
        raise ValueError("Input text is empty.")
    text = text.lower()
    return text

def detect_language(text):
    """주어진 텍스트의 언어를 감지합니다."""
    try:
        if isinstance(text, str):
            return detect(text)
        else:
            logger.error("문자열이 아닌 객체 전달됨")
            return None
    except Exception as e:
        logger.error(f"Language detection failed: {e}")
        return None

def sentences_from_text(text, max_length=500):
    """
    텍스트를 문장 단위로 분할합니다.
    """
    import re
    sentences = re.split(r'(?<=[.!?]) +', text)  # 문장 분할
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) <= max_length:
            current_chunk += sentence + " "
        else:
            chunks.append(current_chunk.strip())
            current_chunk = sentence + " "

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks

def split_text(text, max_tokens=500):
    """
    텍스트를 최대 토큰 수에 맞게 분할합니다.
    """
    words = text.split()
    chunks = [" ".join(words[i:i + max_tokens]) for i in range(0, len(words), max_tokens)]
    return chunks

def generate_summary(text, batch_size=10, max_length=500):
    """
    주어진 텍스트를 요약합니다.
    """
    # 언어 감지
    language = detect_language(text)
    if not language:
        return "Failed to detect language. Please provide text in a supported language."

    # 지원되는 언어인지 확인
    if language not in supported_languages:
        return f"Unsupported language: {language}. Summarization available for: {', '.join(supported_languages.keys())}"

    # 언어별 요약 모델 로드
    try:
        summarizer = pipeline("summarization", model=supported_languages[language], device=0)
        logger.info(f"Loaded summarization model for language: {language}")
    except Exception as e:
        logger.error(f"Error loading summarization model for {language}: {e}")
        return "Failed to load summarization model."
    
    # 텍스트를 청크로 분할
    chunks = split_text(text)
    logger.info(f"Text split into {len(chunks)} chunks.")

    # Dataset 생성
    dataset = Dataset.from_dict({"text": chunks})

    # 배치 요약 함수
    def batch_summarize(batch):
        try:
            summaries = summarizer(batch["text"], max_length=200, min_length=30, truncation=True)
            return {"summary": [s["summary_text"] for s in summaries]}
        except Exception as e:
            logger.error(f"Error in batch summarization: {e}")
            return {"summary": ["Error summarizing text."] * len(batch["text"])}

    # 배치 처리
    summaries = dataset.map(batch_summarize, batched=True, batch_size=batch_size)
    return summaries["summary"]

    
def extract_text_from_pdf(file):
    file.seek(0)
    reader = PyPDF2.PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def extract_text_from_epub(file):
    """EPUB 파일에서 텍스트를 추출합니다."""
    temp_file_path = None

    # FileStorage 객체 처리
    if isinstance(file, FileStorage):
        temp_file_path = os.path.join("tmp", file.filename)
        try:
            os.makedirs("tmp", exist_ok=True)
            file.save(temp_file_path)  # 디스크에 저장
            file_path = temp_file_path
        except Exception as e:
            logger.error(f"임시 파일 저장 실패: {e}")
            return {"message": f"임시 파일 저장 실패: {e}"}
    else:
        file_path = file  # 이미 파일 경로인 경우

    # EPUB 텍스트 추출
    try:
        book = epub.read_epub(file_path, options={'ignore_ncx': True})
        text = ""
        for item in book.get_items():
            if item.media_type == 'application/xhtml+xml':
                soup = BeautifulSoup(item.get_body_content(), 'html.parser')
                text += soup.get_text(separator="\n") + "\n"
        return text
    except Exception as e:
        logger.error(f"EPUB 처리 실패: {e}")
        return {"message": f"EPUB 처리 실패: {e}"}
    finally:
        # 임시 파일 삭제
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logger.error(f"임시 파일 삭제 실패: {e}")

def extract_text_from_docx(file):
    doc = docx.Document(file)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text

def extract_text_from_txt(file):
    return file.read().decode("utf-8")

# def preprocess_text(text):
#     text = unicodedata.normalize('NFKD', text)  # 유니코드 정규화
#     text = re.sub(r'[^\w\s]', '', text)
#     text = re.sub(r'\s+', ' ', text).strip()
#     return text

def extract_text(file, file_format):
    file.seek(0)  # 파일 포인터를 처음으로 되돌림
    if file_format == 'pdf':
        return extract_text_from_pdf(file)
    elif file_format == 'epub':
        return extract_text_from_epub(file)
    elif file_format == 'docx':
        return extract_text_from_docx(file)
    elif file_format == 'txt':
        return extract_text_from_txt(file)
    else:
        raise ValueError("Unsupported file format")

def generate_metadata(text):
        # 텍스트 전처리
    text = preprocess_text(text)
    
    # TF-IDF 벡터화
    vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
    tfidf_matrix = vectorizer.fit_transform([text])
    
    # 단어와 TF-IDF 점수 매핑
    feature_names = vectorizer.get_feature_names_out()
    tfidf_scores = tfidf_matrix.toarray()[0]
    
    # TF-IDF 점수가 높은 순서로 단어 정렬
    sorted_indices = np.argsort(tfidf_scores)[::-1]
    
    # 메타데이터 생성
    metadata = [
        {"tag": "Language", "value": detect_language(text)},
        {"tag": "Length", "value": f"{len(text)} characters"},
        {"tag": "Pages", "value": f"{len(text) // 1500} pages"},
        {"tag": "Complexity", "value": "High" if len(text.split()) > 1000 else "Medium" if len(text.split()) > 500 else "Low"}
    ]
    return metadata