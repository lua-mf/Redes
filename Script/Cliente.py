import socket
import threading
from time import sleep
import random  # Para simular erro/perda com probabilidade
import time


def calcular_checksum(pacote):
    return sum(ord(char) for char in pacote) % 256

HOST = '127.0.0.1'
PORT = 50000

# Modo de operação
print("Selecione o modo de operação:")
print("1 - Go-Back-N")
print("2 - Repetição Seletiva")

while True:
    try:
        modo_operacao = int(input("Digite o número do modo (1 ou 2): "))
        if modo_operacao in [1, 2]:
            break
        else:
            print("Entrada inválida. Digite 1 ou 2.")
    except ValueError:
        print("Entrada inválida. Digite apenas números.")

# Limite máximo de caracteres enviado por vez
while True:
    try:
        limite_max = int(input("Digite o tamanho máximo da mensagem: ")) # quantidade de chars por comunicação
        if 1 <= limite_max:
            break
    except ValueError:
        print("Entrada inválida. Digite apenas números.")

# Modo de envio
print("\nSelecione o modo de envio:")
print("1 - Individual")
print("2 - Lote")

while True:
    try:
        modo_envio = int(input("Digite o número do modo de envio (1 ou 2): "))
        if modo_envio in [1, 2]:
            break
        else:
            print("Entrada inválida. Digite 1 ou 2.")
    except ValueError:
        print("Entrada inválida. Digite apenas números.")

# Tamanho de janela fixo em 4 com controle de congestionamento
if modo_envio == 2:
    tamanho_janela_inicial = 4  # Tamanho inicial fixo da janela
    tamanho_janela = tamanho_janela_inicial  # Tamanho atual da janela
    print(f"Tamanho da janela inicial: {tamanho_janela}")
else:
    tamanho_janela = 1  # No modo individual, a janela é sempre 1

# Cliente digita a mensagem completa
while True:
    mensagem = input("\nDigite a mensagem completa para enviar: ")
    if len(mensagem) > limite_max:
        print(f"Mensagem maior do que o limite máximo de {limite_max} caracteres")
    else:
        break

# Simulação separada de erros e perdas
simular_perdas = input("\nDeseja simular PERDA de pacotes automaticamente? (s/n): ").strip().lower() == 's'
if simular_perdas:
    prob_perda = float(input("Probabilidade de PERDA (0 a 1): "))
else:
    prob_perda = 0.0

simular_erros = input("Deseja simular ERROS de pacotes automaticamente? (s/n): ").strip().lower() == 's'
if simular_erros:
    prob_erro = float(input("Probabilidade de ERRO (0 a 1): "))
else:
    prob_erro = 0.0

# Divide a mensagem em pacotes conforme tamanho máximo de 3 caracteres por pacote
pacotes = [mensagem[i:i+3] for i in range(0, len(mensagem), 3)]
qtd_pacotes = len(pacotes)

# Criação do socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)

# Sistema de temporizadores
timers = {}  # Dicionário para guardar temporizadores individuais (usado no modo individual)
lock = threading.Lock()  # Lock para sincronização
pacotes_enviados = {}  # Status dos pacotes (enviados mas não confirmados)
base = 1  # Base da janela (próximo pacote esperando confirmação)
proximo_seq = 1  # Próximo número de sequência a ser usado
timer = None  # Timer para Go-Back-N no modo lote (um único timer para a janela inteira)

# Variáveis de controle de congestionamento
nacks_consecutivos = 0  # Contador de NACKs consecutivos
threshold = 8  # Limite para o controle de congestionamento
tamanho_janela_min = 1  # Tamanho mínimo da janela

def temporizador_base():
    """Função chamada quando o temporizador da base expira no Go-Back-N"""
    global timer, nacks_consecutivos, tamanho_janela
    
    print(f"[DEBUG] Temporizador da base {base} expirou! Hora: {time.strftime('%H:%M:%S')}")

    with lock:
        print(f"[TIMEOUT] Sem resposta para a janela a partir da base {base}. Reenviando todos os pacotes...")
        # Timeout também é considerado um erro de transmissão
        nacks_consecutivos += 1
        # Reduzir o tamanho da janela em caso de timeout
        if modo_envio == 2 and nacks_consecutivos > 0:
            tamanho_janela_antigo = tamanho_janela
            tamanho_janela = max(tamanho_janela // 2, tamanho_janela_min)
            if tamanho_janela_antigo != tamanho_janela:
                print(f"[CONGESTIONAMENTO] Janela reduzida de {tamanho_janela_antigo} para {tamanho_janela} após timeout")
        
        # Reenvia todos os pacotes a partir da base
        for i in range(base, min(base + tamanho_janela, proximo_seq)):
            if i <= qtd_pacotes:
                enviar_pacote_sem_timer(i, pacotes[i-1])
        
        # Reinicia o temporizador
        timer = threading.Timer(2.0, temporizador_base)
        timer.start()
        print(f"[DEBUG] Timer da base {base} reiniciado após timeout! Hora: {time.strftime('%H:%M:%S')}")

def iniciar_timer_base():
    """Inicia ou reinicia o temporizador da base para Go-Back-N"""
    global timer
    
    # Cancela o timer anterior se existir
    if timer is not None:
        timer.cancel()
    
    # Cria e inicia um novo timer
    timer = threading.Timer(2.0, temporizador_base)
    timer.start()
    print(f"[DEBUG] Timer da base {base} iniciado! Hora: {time.strftime('%H:%M:%S')}")

def timer_individual(idx, pacote):
    """Função chamada quando um temporizador individual expira"""
    global nacks_consecutivos, tamanho_janela
    
    print(f"[TIMEOUT] Sem resposta para o pacote {idx}. Reenviando...")
    # Timeout também é considerado um erro de transmissão
    nacks_consecutivos += 1
    
    # Reduzir o tamanho da janela em caso de timeout
    if modo_envio == 2 and nacks_consecutivos > 0:
        tamanho_janela_antigo = tamanho_janela
        tamanho_janela = max(tamanho_janela // 2, tamanho_janela_min)
        if tamanho_janela_antigo != tamanho_janela:
            print(f"[CONGESTIONAMENTO] Janela reduzida de {tamanho_janela_antigo} para {tamanho_janela} após timeout")
    
    enviar_pacote_sem_timer(idx, pacote)
    
    # Reinicia o temporizador
    timers[idx] = threading.Timer(2.0, lambda: timer_individual(idx, pacote))
    timers[idx].start()

def enviar_pacote(idx, pacote):
    """Envia um pacote e gerencia temporizadores conforme o modo de operação"""
    global timer
    
    # checksum = calcular_checksum(pacote)

    # Simulação de perda
    if simular_perdas and random.random() < prob_perda:
        print(f"[SIMULAÇÃO] Pacote {idx} NÃO enviado (simulação de PERDA).")
        ###return

        ###########
        # Se for o pacote base e estamos no modo Go-Back-N, precisamos garantir que o timer seja iniciado
        if idx == base and modo_operacao == 1 and modo_envio == 2:
            print(f"[DEBUG] Iniciando timer para o pacote base {base} mesmo após perda simulada")
            iniciar_timer_base()
            
        return False  # Indica que o pacote não foi enviado
        ###########
    # Simulação de erro
    if simular_erros and random.random() < prob_erro:
        checksum = (calcular_checksum(pacote) + 1) % 256
        print(f"[SIMULAÇÃO] Pacote {idx} enviado com CHECKSUM ERRADO.")
    else:
        checksum = calcular_checksum(pacote)

    pacote_enviado = f"{checksum:03d}|{idx:03d}|{pacote}"
    try:
        s.sendall(pacote_enviado.encode())
        print(f"Pacote {idx} enviado: '{pacote_enviado}'")
        pacotes_enviados[idx] = True
    except Exception as e:
        print(f"Erro ao enviar pacote {idx}: {e}")
        return False

    # Gerencia temporizadores de forma diferente para cada modo
    if modo_envio == 1:  # Individual
        # No modo individual, cada pacote tem seu próprio temporizador
        if idx in timers:
            timers[idx].cancel()
        timers[idx] = threading.Timer(2.0, lambda: timer_individual(idx, pacote))
        timers[idx].start()
    else:  # Lote
        if modo_operacao == 1:  # Go-Back-N
            if idx == base:  # Apenas iniciar o timer quando for o pacote base
                iniciar_timer_base()
        else:  # Repetição Seletiva - cada pacote tem seu próprio timer
            def timeout_seletivo():
                with lock:
                    if idx in pacotes_enviados:  # Ainda não foi confirmado
                        print(f"[TIMEOUT] Sem resposta para o pacote {idx}. Reenviando...")
                        # Timeout também é considerado um erro de transmissão
                        global nacks_consecutivos, tamanho_janela
                        nacks_consecutivos += 1
                        
                        # Reduzir o tamanho da janela em caso de timeout
                        if nacks_consecutivos > 0:
                            tamanho_janela_antigo = tamanho_janela
                            tamanho_janela = max(tamanho_janela // 2, tamanho_janela_min)
                            if tamanho_janela_antigo != tamanho_janela:
                                print(f"[CONGESTIONAMENTO] Janela reduzida de {tamanho_janela_antigo} para {tamanho_janela} após timeout")
                        
                        enviar_pacote_sem_timer(idx, pacote)
                        # Reinicia o temporizador
                        timer_individual = threading.Timer(2.0, timeout_seletivo)
                        timer_individual.start()
                        pacotes_enviados[idx] = (timer_individual, True)  # Armazena o timer e estado
            
            # Inicia o temporizador para este pacote específico (Repetição Seletiva)
            timer_individual = threading.Timer(2.0, timeout_seletivo)
            timer_individual.start()
            pacotes_enviados[idx] = (timer_individual, True)  # Armazena o timer e estado
    return True  # Indica que o pacote foi enviado

def enviar_pacote_sem_timer(idx, pacote):
    """Envia um pacote sem gerenciar temporizadores (usado em retransmissões)"""
    checksum = calcular_checksum(pacote)
    pacote_enviado = f"{checksum:03d}|{idx:03d}|{pacote}"
    try:
        s.sendall(pacote_enviado.encode())
        print(f"Pacote {idx} reenviado: '{pacote_enviado}'")
    except Exception as e:
        print(f"Erro ao reenviar pacote {idx}: {e}")

def cancelar_timers():
    """Cancela todos os temporizadores ativos"""
    global timer
    
    # Cancela o timer principal do Go-Back-N
    if timer is not None:
        timer.cancel()
    
    # Cancela os timers individuais
    for t in timers.values():
        if isinstance(t, threading.Timer):
            t.cancel()
    
    # Cancela os timers do Repetição Seletiva
    if modo_operacao == 2 and modo_envio == 2:  # Repetição Seletiva em lote
        for idx in list(pacotes_enviados.keys()):
            if isinstance(pacotes_enviados[idx], tuple):
                timer_individual, _ = pacotes_enviados[idx]
                timer_individual.cancel()

def verificador_de_timeout():
    """Thread para verificar periodicamente se o timer da base está funcionando"""
    global base, timer
    
    while base <= qtd_pacotes:
        time.sleep(3)  # Verifica a cada 3 segundos
        with lock:
            if base <= qtd_pacotes and timer is None and modo_operacao == 1 and modo_envio == 2:
                print(f"[ALERTA] Timer da base {base} não está ativo! Reiniciando...")
                iniciar_timer_base()

def thread_receptor():
    """Thread para receber e processar ACKs/NACKs do servidor"""
    global base, proximo_seq, timer, tamanho_janela, nacks_consecutivos
    
    while base <= qtd_pacotes:
        try:
            resposta = s.recv(1024).decode()

            # Dividir respostas concatenadas
            respostas = resposta.replace("ack|", "\nack|").replace("nack|", "\nnack|").replace("todos_pacotes_recebidos", "\ntodos_pacotes_recebidos").split("\n")
            for resp in respostas:
                if not resp:
                    continue

                if resp.startswith("ack|"):
                    try:
                        numero_texto = resp.split("ack|")[1].split()[0]
                        numero_pacote = int(numero_texto)
                        print(f"[ACK] Pacote {numero_pacote} confirmado.")
                        
                        # ACK bem-sucedido, zerar contador de NACKs consecutivos
                        nacks_consecutivos = 0
                        
                        # Em caso de transmissão bem-sucedida, aumentamos gradualmente o tamanho da janela
                        if modo_envio == 2:
                            # Se já alcançamos o threshold, cresce linearmente (+1)
                            if tamanho_janela >= threshold:
                                if tamanho_janela < 2 * threshold:  # Limite máximo da janela
                                    tamanho_janela_antigo = tamanho_janela
                                    tamanho_janela += 1
                                    print(f"[CONGESTIONAMENTO] Janela aumentada linearmente de {tamanho_janela_antigo} para {tamanho_janela}")
                            else:
                                # Antes do threshold, cresce exponencialmente (dobra)
                                tamanho_janela_antigo = tamanho_janela
                                tamanho_janela = min(tamanho_janela * 2, threshold)
                                if tamanho_janela_antigo != tamanho_janela:
                                    print(f"[CONGESTIONAMENTO] Janela aumentada exponencialmente de {tamanho_janela_antigo} para {tamanho_janela}")
                    except Exception as e:
                        print(f"Erro ao processar ACK: {e}")
                        continue

                    with lock:
                        if modo_envio == 1:  # Individual
                            # Cancela o temporizador individual
                            if numero_pacote in timers:
                                timers[numero_pacote].cancel()      
                        else:  # Lote
                            if modo_operacao == 1:  # Go-Back-N
                                # No Go-Back-N, confirma cumulativamente até o número recebido
                                if numero_pacote >= base:
                                    # Remove todos os pacotes até numero_pacote da lista de enviados
                                    for i in range(base, numero_pacote + 1):
                                        if i in pacotes_enviados:
                                            del pacotes_enviados[i]
                                    # Atualiza a base para o próximo pacote não confirmado
                                    base = numero_pacote + 1

                                    # Avanço da janela
                                    while proximo_seq < base + tamanho_janela and proximo_seq <= qtd_pacotes:
                                            enviar_pacote(proximo_seq, pacotes[proximo_seq-1])
                                            proximo_seq += 1
                                    
                                    # Reinicia o temporizador para a nova base (se ainda houver pacotes a confirmar)
                                    if base <= qtd_pacotes:
                                        iniciar_timer_base()
                                    else:
                                        # Todos os pacotes foram confirmados, cancela o temporizador
                                        if timer is not None:
                                            timer.cancel()
                                            timer = None
                            
                            else:  # Repetição Seletiva
                                # No Repetição Seletiva, confirma apenas o pacote específico
                                if numero_pacote in pacotes_enviados:
                                    # Cancela o temporizador individual
                                    if isinstance(pacotes_enviados[numero_pacote], tuple):
                                        timer_individual, _ = pacotes_enviados[numero_pacote]
                                        timer_individual.cancel()
                                    
                                    # Remove o pacote da lista de enviados
                                    del pacotes_enviados[numero_pacote]
                                    
                                    # Verifica se a base pode avançar
                                    while base not in pacotes_enviados and base <= qtd_pacotes:
                                        base += 1
                                    
                                    # Envia mais pacotes se possível
                                    while proximo_seq < base + tamanho_janela and proximo_seq <= qtd_pacotes:
                                        enviar_pacote(proximo_seq, pacotes[proximo_seq-1])
                                        proximo_seq += 1

                elif resp.startswith("nack|"):
                    try:
                        numero_pacote = int(resp.split("|")[1])
                        print(f"[NACK] Erro no pacote {numero_pacote}, reenviando...")
                        
                        # Incrementar contador de NACKs consecutivos e reduzir tamanho da janela
                        nacks_consecutivos += 1
                        
                        # Reduzir tamanho da janela em caso de NACK (modo lote)
                        if modo_envio == 2:
                            tamanho_janela_antigo = tamanho_janela
                            # Se recebemos NACK, voltamos ao slow start (reduz pela metade)
                            tamanho_janela = max(tamanho_janela // 2, tamanho_janela_min)
                            if tamanho_janela_antigo != tamanho_janela:
                                print(f"[CONGESTIONAMENTO] Janela reduzida de {tamanho_janela_antigo} para {tamanho_janela} após NACK")
                    except Exception as e:
                        print(f"Erro ao processar NACK: {e}")
                        continue

                    with lock:
                        if modo_envio == 1:  # Individual
                            # Cancela o temporizador individual
                            if numero_pacote in timers:
                                timers[numero_pacote].cancel()
                            # Reenvia o pacote específico
                            if numero_pacote <= qtd_pacotes:
                                enviar_pacote(numero_pacote, pacotes[numero_pacote-1])
                        else:  # Lote
                            if modo_operacao == 1:  # Go-Back-N
                                # No Go-Back-N, volta a base para o pacote com erro
                                base = numero_pacote
                                
                                # Reenvia todos os pacotes a partir da base, limitado pelo tamanho atual da janela
                                for i in range(base, min(base + tamanho_janela, proximo_seq)):
                                    if i <= qtd_pacotes:
                                        enviar_pacote_sem_timer(i, pacotes[i-1])
                                
                                # Reinicia o temporizador para a nova base
                                iniciar_timer_base()
                            
                            else:  # Repetição Seletiva
                                # No Repetição Seletiva, reenvia apenas o pacote com erro
                                if numero_pacote <= qtd_pacotes:
                                    # Cancela o temporizador anterior
                                    if numero_pacote in pacotes_enviados and isinstance(pacotes_enviados[numero_pacote], tuple):
                                        timer_individual, _ = pacotes_enviados[numero_pacote]
                                        timer_individual.cancel()
                                    
                                    # Reenvia o pacote
                                    enviar_pacote(numero_pacote, pacotes[numero_pacote-1])

                elif resp.strip() == "todos_pacotes_recebidos":
                    print("\nServidor confirmou recebimento de todos os pacotes.")
                    return

        except socket.timeout:
            continue
        except Exception as e:
            print(f"Erro na thread receptora: {e}")
            break
        
try:
    s.connect((HOST, PORT))
    print(f"\nConectado ao servidor {HOST}:{PORT}")
    
    # Envia handshake
    mensagem_handshake = f"modo={modo_operacao},limite máximo={limite_max}, envio={modo_envio},qtd_pacotes={qtd_pacotes},janela={tamanho_janela}"
    s.sendall(mensagem_handshake.encode())
    
    resposta = s.recv(1024).decode()
    
    if resposta == "ack_handshake":
        print("Handshake concluído com sucesso.\n")
        
        if modo_envio == 1:  # Modo Individual
            print("Enviando em modo INDIVIDUAL...\n")
            for idx, pacote in enumerate(pacotes, 1):
                enviar_pacote(idx, pacote)
                sleep(0.5)

                tentativas = 0
                while tentativas < 5:
                    try:
                        resposta = s.recv(1024).decode()
                        if resposta.startswith("ack|"):
                            numero_pacote = int(resposta.split("|")[1])
                            print(f"[ACK] Pacote {numero_pacote} confirmado.")
                            if numero_pacote in timers:
                                timers[numero_pacote].cancel()
                            break
                        elif resposta.startswith("nack|"):
                            numero_pacote = int(resposta.split("|")[1])
                            print(f"[NACK] Erro no pacote {numero_pacote}, reenviando...")
                            if numero_pacote in timers:
                                timers[numero_pacote].cancel()
                            enviar_pacote(numero_pacote, pacotes[numero_pacote-1])
                    except socket.timeout:
                        tentativas += 1
                        print(f"[TIMEOUT] Tentativa {tentativas} aguardando ACK/NACK para pacote {idx}...")
                
                if tentativas == 5:
                    print(f"[ERRO] Pacote {idx} falhou após múltiplas tentativas. Encerrando envio.")
                    break

                if idx < len(pacotes):
                    sleep(1)

        else:  # Modo Lote (Janela Deslizante)
            print(f"Enviando em modo LOTE com janela de controle de congestionamento (inicial={tamanho_janela})...\n")
            
            # Inicia thread para receber ACKs/NACKs
            receptor = threading.Thread(target=thread_receptor)
            receptor.daemon = True
            receptor.start()
            
            # Adicione o verificador de timeout
            verificador = threading.Thread(target=verificador_de_timeout)
            verificador.daemon = True
            verificador.start()

            # Envia os primeiros pacotes (até o tamanho da janela)
            with lock:
                while proximo_seq <= min(tamanho_janela, qtd_pacotes):
                    enviar_pacote(proximo_seq, pacotes[proximo_seq-1])
                    proximo_seq += 1
            
            #########
            # Garantir que o timer da base seja iniciado mesmo se o primeiro pacote for perdido
            if proximo_seq == 2 and modo_operacao == 1:  # Go-Back-N
                print("[DEBUG] Verificando se o timer da base foi iniciado...")
            if timer is None:
                print("[DEBUG] Timer da base não foi iniciado! Iniciando agora...")
                iniciar_timer_base()
            ##########

            # Aguarda até que todos os pacotes sejam confirmados
            while base <= qtd_pacotes:
                sleep(0.1)

        print("\nAguardando últimas confirmações...")
        sleep(5)  # Espera 5 segundos para ver todos os ACKs
    
        print("\nTodos os pacotes foram enviados e confirmados.")
            
    elif resposta == "nack_handshake":
        print("Servidor rejeitou o handshake. Verifique os parâmetros e tente novamente.")
    else:
        print(f"Resposta inesperada do servidor: {resposta}")

except Exception as e:
    print(f"Ocorreu um erro: {e}")
finally:
    cancelar_timers()
    s.close()
    print("Conexão fechada.")