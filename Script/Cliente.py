import socket
import threading
from time import sleep

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

# limite máximo de caracteres enviado por vez
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

if modo_envio == 2:
    while True:
        try:
            tamanho_janela = int(input("Digite o tamanho da janela (para envio em lote): "))
            if 1 <= tamanho_janela <= 10:
                break
            else:
                print("Tamanho inválido. Digite um número entre 1 e 10.")
        except ValueError:
            print("Entrada inválida. Digite apenas números.")
else:
    tamanho_janela = 1  # No modo individual, a janela é sempre 1

# Cliente digita a mensagem completa
while True:
    mensagem = input("\nDigite a mensagem completa para enviar: ")
    if len(mensagem) > limite_max:
        print(f"Mensagem maior do que o limite máximo de {limite_max} caracteres")
    else:
        break

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

def temporizador_base():
    """Função chamada quando o temporizador da base expira no Go-Back-N"""
    global timer
    
    with lock:
        print(f"[TIMEOUT] Sem resposta para a janela a partir da base {base}. Reenviando todos os pacotes...")
        # Reenvia todos os pacotes a partir da base
        for i in range(base, proximo_seq):
            if i <= qtd_pacotes:
                enviar_pacote_sem_timer(i, pacotes[i-1])
        
        # Reinicia o temporizador
        timer = threading.Timer(2.0, temporizador_base)
        timer.start()

def iniciar_timer_base():
    """Inicia ou reinicia o temporizador da base para Go-Back-N"""
    global timer
    
    # Cancela o timer anterior se existir
    if timer is not None:
        timer.cancel()
    
    # Cria e inicia um novo timer
    timer = threading.Timer(2.0, temporizador_base)
    timer.start()

def timer_individual(idx, pacote):
    """Função chamada quando um temporizador individual expira"""
    print(f"[TIMEOUT] Sem resposta para o pacote {idx}. Reenviando...")
    enviar_pacote_sem_timer(idx, pacote)
    
    # Reinicia o temporizador
    timers[idx] = threading.Timer(2.0, lambda: timer_individual(idx, pacote))
    timers[idx].start()

def enviar_pacote(idx, pacote):
    """Envia um pacote e gerencia temporizadores conforme o modo de operação"""
    global timer
    
    checksum = calcular_checksum(pacote)
    pacote_enviado = f"{checksum:03d}|{idx:03d}|{pacote}"
    try:
        s.sendall(pacote_enviado.encode())
        print(f"Pacote {idx} enviado: '{pacote_enviado}'")
        pacotes_enviados[idx] = True
    except Exception as e:
        print(f"Erro ao enviar pacote {idx}: {e}")
        return

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
                        enviar_pacote_sem_timer(idx, pacote)
                        # Reinicia o temporizador
                        timer_individual = threading.Timer(2.0, timeout_seletivo)
                        timer_individual.start()
                        pacotes_enviados[idx] = (timer_individual, True)  # Armazena o timer e estado
            
            # Inicia o temporizador para este pacote específico (Repetição Seletiva)
            timer_individual = threading.Timer(2.0, timeout_seletivo)
            timer_individual.start()
            pacotes_enviados[idx] = (timer_individual, True)  # Armazena o timer e estado

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

def thread_receptor():
    """Thread para receber e processar ACKs/NACKs do servidor"""
    global base, proximo_seq, timer
    
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
                                
                                # Reenvia todos os pacotes a partir da base
                                for i in range(base, proximo_seq):
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
            print(f"Enviando em modo LOTE com janela de tamanho {tamanho_janela}...\n")
            
            # Inicia thread para receber ACKs/NACKs
            receptor = threading.Thread(target=thread_receptor)
            receptor.daemon = True
            receptor.start()
            
            # Envia os primeiros pacotes (até o tamanho da janela)
            with lock:
                while proximo_seq <= min(tamanho_janela, qtd_pacotes):
                    enviar_pacote(proximo_seq, pacotes[proximo_seq-1])
                    proximo_seq += 1
            
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