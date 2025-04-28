import socket
import threading
from time import sleep

def calcular_checksum(pacote):
    return sum(ord(char) for char in pacote) % 256

HOST = '127.0.0.1'
PORT = 50000

# Configuração inicial
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

while True:
    try:
        tamanho_max = int(input("Digite o tamanho máximo do pacote (1 a 3): "))
        if 1 <= tamanho_max <= 3:
            break
        else:
            print("Entrada inválida. Digite um número entre 1 e 3.")
    except ValueError:
        print("Entrada inválida. Digite apenas números.")

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
mensagem = input("\nDigite a mensagem completa para enviar: ")

# Divide a mensagem em pacotes conforme tamanho máximo
pacotes = [mensagem[i:i+tamanho_max] for i in range(0, len(mensagem), tamanho_max)]
qtd_pacotes = len(pacotes)

# Criação do socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)

timers = {}  # Dicionário para guardar temporizadores
lock = threading.Lock()  # Lock para sincronização
pacotes_enviados = {}  # Status dos pacotes (enviados mas não confirmados)
base = 1  # Base da janela (próximo pacote esperando confirmação)
proximo_seq = 1  # Próximo número de sequência a ser usado

def enviar_pacote(idx, pacote):
    def timeout():
        with lock:
            # Verificar se o pacote ainda precisa ser reenviado
            if idx in pacotes_enviados:
                print(f"[TIMEOUT] Sem resposta para o pacote {idx}. Reenviando...")
                if modo_operacao == 1:  # Go-Back-N
                    # Reenvia todos os pacotes da janela atual
                    for i in range(base, proximo_seq):
                        if i <= qtd_pacotes:
                            enviar_pacote_sem_timer(i, pacotes[i-1])
                else:  # Repetição seletiva
                    # Reenvia apenas o pacote que expirou
                    enviar_pacote_sem_timer(idx, pacote)
                
                # Reinicia o temporizador
                timer = threading.Timer(2.0, timeout)
                timer.start()
                timers[idx] = timer

    checksum = calcular_checksum(pacote)
    pacote_enviado = f"{checksum:03d}|{idx:03d}|{pacote}"
    try:
        s.sendall(pacote_enviado.encode())
        print(f"Pacote {idx} enviado: '{pacote_enviado}'")
    except Exception as e:
        print(f"Erro ao enviar pacote {idx}: {e}")
        return

    # Cancela timer antigo se já existir
    if idx in timers:
        timers[idx].cancel()

    # Inicia novo temporizador para este pacote
    timer = threading.Timer(2.0, timeout)
    timer.start()
    timers[idx] = timer

def enviar_pacote_sem_timer(idx, pacote):
    checksum = calcular_checksum(pacote)
    pacote_enviado = f"{checksum:03d}|{idx:03d}|{pacote}"
    try:
        s.sendall(pacote_enviado.encode())
        print(f"Pacote {idx} reenviado: '{pacote_enviado}'")
    except Exception as e:
        print(f"Erro ao reenviar pacote {idx}: {e}")

def thread_receptor():
    global base, proximo_seq
    
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
                        if numero_pacote in timers:
                            timers[numero_pacote].cancel()
                            del timers[numero_pacote]
                        
                        if numero_pacote in pacotes_enviados:
                            del pacotes_enviados[numero_pacote]

                        if modo_operacao == 1:  # Go-Back-N
                            if numero_pacote == base:
                                base += 1
                                while proximo_seq < base + tamanho_janela and proximo_seq <= qtd_pacotes:
                                    enviar_pacote(proximo_seq, pacotes[proximo_seq-1])
                                    pacotes_enviados[proximo_seq] = True
                                    proximo_seq += 1

                        else:  # Repetição Seletiva
                            while base not in pacotes_enviados and base <= qtd_pacotes:
                                base += 1
                            while proximo_seq < base + tamanho_janela and proximo_seq <= qtd_pacotes:
                                enviar_pacote(proximo_seq, pacotes[proximo_seq-1])
                                pacotes_enviados[proximo_seq] = True
                                proximo_seq += 1

                elif resp.startswith("nack|"):
                    try:
                        numero_pacote = int(resp.split("|")[1])
                        print(f"[NACK] Erro no pacote {numero_pacote}, reenviando...")
                    except Exception as e:
                        print(f"Erro ao processar NACK: {e}")
                        continue

                    with lock:
                        if numero_pacote in timers:
                            timers[numero_pacote].cancel()

                        if modo_operacao == 1:  # Go-Back-N
                            base = numero_pacote
                            for i in range(base, proximo_seq):
                                if i <= qtd_pacotes:
                                    enviar_pacote(i, pacotes[i-1])
                                    pacotes_enviados[i] = True
                        else:  # Repetição Seletiva
                            if numero_pacote <= qtd_pacotes:
                                enviar_pacote(numero_pacote, pacotes[numero_pacote-1])
                                pacotes_enviados[numero_pacote] = True

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
    mensagem_handshake = f"modo={modo_operacao},tamanho={tamanho_max},envio={modo_envio},qtd_pacotes={qtd_pacotes},janela={tamanho_janela}"
    s.sendall(mensagem_handshake.encode())
    
    resposta = s.recv(1024).decode()
    
    if resposta == "ack_handshake":
        print("Handshake concluído com sucesso.\n")
        
        if modo_envio == 1:
            print("Enviando em modo INDIVIDUAL...\n")
            for idx, pacote in enumerate(pacotes, 1):
                enviar_pacote(idx, pacote)

                tentativas = 0
                while tentativas < 5:
                    try:
                        resposta = s.recv(1024).decode()
                        if resposta.startswith("ack|"):
                            numero_pacote = int(resposta.split("|")[1])
                            print(f"[ACK] Pacote {numero_pacote} confirmado.")
                            timers[numero_pacote].cancel()
                            break
                        elif resposta.startswith("nack|"):
                            numero_pacote = int(resposta.split("|")[1])
                            print(f"[NACK] Erro no pacote {numero_pacote}, reenviando...")
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
                    pacotes_enviados[proximo_seq] = True  # Adicionar esta linha
                    proximo_seq += 1
            
            # Aguarda até que todos os pacotes sejam confirmados
            while base <= qtd_pacotes:
                sleep(0.1)

        print("\nAguardando últimas confirmações...")
        sleep(5)  # Espera 2 segundos para ver todos os ACKs
    
        print("\nTodos os pacotes foram enviados e confirmados.")
            
    elif resposta == "nack_handshake":
        print("Servidor rejeitou o handshake. Verifique os parâmetros e tente novamente.")
    else:
        print(f"Resposta inesperada do servidor: {resposta}")

except Exception as e:
    print(f"Ocorreu um erro: {e}")
finally:
    for t in timers.values():
        t.cancel()
    s.close()
    print("Conexão fechada.")
