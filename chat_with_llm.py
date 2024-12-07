import praw
import requests
import streamlit as st
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from dotenv import load_dotenv, find_dotenv
import re
from PIL import Image
from io import BytesIO
import json
import time

# Configurações do Telegram
bot_token = '7722332205:AAGQHbd_VOCdKiqli6eh-HpnS07APZTK83w'
chat_id = '-1002218221761'

# Configuração do Reddit
reddit = praw.Reddit(
    user_agent=True,
    client_id='lnZVbq0GY7B6C2Jm4DIU0Q',
    client_secret='LBb-1aLJ3TUNP8LOxUlzHJHcTTu-Xw',
    username='Stock_Might396',
    password='Voidka123'
)


def is_valid_image_url(url):
    """Verifica se a URL é uma imagem válida e acessível."""
    try:
        response = requests.head(url, allow_redirects=True, timeout=5)
        content_type = response.headers.get('content-type', '').lower()
        return 'image' in content_type
    except:
        return False


def get_image_url(post):
    """Extrai a URL da imagem do post do Reddit."""
    try:
        # Verifica se é uma galeria
        if hasattr(post, 'is_gallery') and post.is_gallery:
            try:
                # Tenta pegar a primeira imagem da galeria
                media_metadata = post.media_metadata
                first_image = list(media_metadata.values())[0]
                return first_image['p'][0]['u']
            except:
                return None

        # Verifica se é uma imagem direta
        elif hasattr(post, 'url'):
            url = post.url.lower()
            if any(url.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                return post.url

            # Tenta pegar preview de mídia se disponível
            elif hasattr(post, 'preview'):
                try:
                    return post.preview['images'][0]['source']['url']
                except:
                    pass

        # Se for um post do Reddit com mídia
        if hasattr(post, 'media') and post.media:
            if 'oembed' in post.media:
                try:
                    return post.media['oembed']['thumbnail_url']
                except:
                    pass
    except Exception as e:
        print(f"Erro ao extrair URL da imagem: {e}")

    return None


def process_image_url(url):
    """Processa a URL da imagem para garantir que seja utilizável."""
    if not url:
        return None

    # Remove caracteres de escape e espaços
    url = url.strip().replace('\\', '')

    # Corrige URLs do Reddit
    if 'preview.redd.it' in url:
        url = url.replace('&amp;', '&')

    return url if is_valid_image_url(url) else None


# Coleta os posts
posts = reddit.subreddit('popular').hot(limit=10)

# Armazenar os dados necessários
post_data = []
for post in posts:
    # Tenta obter a URL da imagem
    image_url = get_image_url(post)
    if image_url:
        image_url = process_image_url(image_url)

        if image_url:  # Se temos uma URL válida
            post_info = {
                'title': post.title,
                'selftext': post.selftext,
                'url': image_url,
                'permalink': f"https://reddit.com{post.permalink}"
            }
            post_data.append(post_info)
            print(f"Post processado com sucesso: {post.title}")
        else:
            print(f"URL inválida para o post: {post.title}")
    else:
        print(f"Sem imagem para o post: {post.title}")

# Sistema e template atualizados
system = """Você é um assistente especializado em análise de sentimentos que considera texto e imagens em suas análises. 
Sua principal função é identificar e descrever detalhadamente tanto elementos visuais quanto textuais presentes nas imagens."""

human_template = """Analise este post do Reddit em detalhes:

TÍTULO: {title}
TEXTO: {text}
IMAGEM: {image_url}

Por favor, forneça:

1. ANÁLISE DA IMAGEM:
   - Se houver texto na imagem: transcreva TODO o texto visível, mantendo sua formatação original
   - Se não houver texto: descreva detalhadamente os elementos visuais (objetos, pessoas, cenário, cores, etc.)
   - Mencione quaisquer elementos gráficos relevantes (memes, símbolos, logotipos, etc.)

2. CONTEXTO:
   - Como a imagem se relaciona com o título
   - Se o texto da imagem (se houver) complementa ou contradiz o título/texto do post
   - Identifique se é um meme, notícia, foto, screenshot, ou outro tipo de conteúdo

3. ANÁLISE DE SENTIMENTO:
   - Avalie o sentimento considerando TODOS os elementos (título, texto do post, imagem e texto na imagem)
   - Forneça porcentagens: negativo:XX%, neutro:XX%, positivo:XX%
   - Justifique sua análise explicando como cada elemento contribuiu para o sentimento geral

4. ALERTA DE CONTEÚDO (se aplicável):
   - Indique se há elementos sensíveis, controversos ou potencialmente problemáticos
   - Mencione se há discrepâncias significativas entre o título e o conteúdo real

Mantenha o formato de sentimento exato: negativo:XX%, neutro:XX%, positivo:XX%"""

prompt = ChatPromptTemplate.from_messages([("system", system), ("human", human_template)])
chat = ChatGroq(
    temperature=0.2,
    model_name="llama-3.2-90b-vision-preview",
    groq_api_key="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"
)
chain = prompt | chat

if "messages" not in st.session_state:
    st.session_state.messages = []

# Interface Streamlit e análise
for post in post_data:
    st.subheader(post['title'])

    # Adiciona link para o post original
    st.markdown(f"[Ver post original no Reddit]({post['permalink']})")

    # Exibe a imagem
    try:
        st.image(post['url'], use_column_width=True)
    except Exception as e:
        st.error(f"Erro ao exibir imagem: {e}")
        continue

    if post['selftext']:
        st.write(post['selftext'])

    # Análise de sentimentos com retry
    max_retries = 3
    retry_count = 0
    while retry_count < max_retries:
        try:
            user_input = {
                'title': post['title'],
                'text': post['selftext'],
                'image_url': post['url']
            }

            response_container = st.chat_message("assistant")
            response_text = response_container.empty()
            full_response = ""

            response_stream = chain.stream(user_input)
            for partial_response in response_stream:
                full_response += str(partial_response.content)
                response_text.markdown(full_response + "▌")

            # Se chegou aqui, a análise foi bem-sucedida
            break

        except Exception as e:
            retry_count += 1
            if retry_count == max_retries:
                st.error(f"Erro na análise após {max_retries} tentativas: {e}")
                continue
            time.sleep(2)  # Pequena pausa antes de tentar novamente

    # Salva a resposta no histórico
    st.session_state.messages.append({"role": "assistant", "content": full_response})

    # Processamento do sentimento negativo e alerta Telegram
    if "negativo" in full_response.lower():
        try:
            match = re.search(r'negativo\s*:\s*(\d+)\s*%', full_response.lower())
            if match:
                negative_percentage = int(match.group(1))
                if negative_percentage > 50:
                    message = f"""🚨 Alerta de Sentimento Negativo 🚨
Título: {post['title']}
Sentimento Negativo: {negative_percentage}%
Link: {post['permalink']}
"""
                    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
                    data = {'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}

                    try:
                        response = requests.post(url, data=data)
                        if response.status_code != 200:
                            st.error(f"Erro ao enviar alerta para o Telegram: {response.text}")
                    except Exception as e:
                        st.error(f"Erro ao enviar mensagem para o Telegram: {e}")

        except Exception as e:
            st.error(f"Erro ao processar sentimento negativo: {e}")

    # Pequena pausa entre análises para evitar sobrecarga
    time.sleep(1)