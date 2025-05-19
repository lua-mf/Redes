import socket
import threading
from time import sleep
import random
import time


def calcular_checksum(pacote):
    return sum(ord(char) for char in pacote) % 256

HOST = '127.0.0.1'
PORT = 50000

# 1. Modo de operação
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

# 2. Tamanho máximo da mensagem
while True:
    try:
        limite_max = int(input("Digite o tamanho máximo da mensagem: "))
        if 1 <= limite_max:
            break
    except ValueError:
        print("Entrada inválida. Digite apenas números.")

# 3. Modo de envio
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

# 4. Simulação de problemas
print("\nSelecione o tipo de simulação:")
print("1 - Normal (sem problemas)")
print("2 - Simular Falha de Integridade")
print("3 - Simular Perda de Pacote")

while True:
    try:
        tipo_simulacao = int(input("Digite o número (1, 2 ou 3): "))
        if tipo_simulacao in [1, 2, 3]:
            break
        else:
            print("Entrada inválida. Digite 1, 2 ou 3.")
    except ValueError:
        print("Entrada inválida. Digite apenas números.")

# Configuração das simulações
if tipo_simulacao == 2:  # Falha de Integridade
    simular_erros = True
    simular_perdas = False
    prob_erro_percentual = int(input("Probabilidade de ERRO em % (0 a 100): "))
    prob_erro = prob_erro_percentual / 100.0
    prob_perda = 0.0
elif tipo_simulacao == 3:  # Perda de Pacote
    simular_erros = False
    simular_perdas = True
    prob_perda_percentual = int(input("Probabilidade de PERDA em % (0 a 100): "))
    prob_perda = prob_perda_percentual / 100.0
    prob_erro = 0.0
else:  # Normal
    simular_erros = False
    simular_perdas = False
    prob_erro = 0.0
    prob_perda = 0.0

# 5. Mensagem a ser enviada
while True:
    mensagem = input("\nDigite a mensagem completa para enviar: ")
    if len(mensagem) > limite_max:
        print(f"Mensagem maior do que o limite máximo de {limite_max} caracteres")
    else:
        break

# Configuração da janela (sempre começa em 1)
tamanho_janela = 1
tamanho_janela_min = 1

# Divide a mensagem em pacotes conforme tamanho máximo de 3 caracteres por pacote
pacotes = [mensagem[i:i+3] for i in range(0, len(mensagem), 3)]
qtd_pacotes = len(pacotes)

# Criação do socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(15)  # Timeout do socket aumentado para 15 segundos

# Sistema de temporizadores
timers = {}
lock = threading.Lock()
pacotes_confirmados = set()  # Pacotes que receberam ACK
base = 1
proximo_seq = 1
timer = None
finalizou = False
buffer_resposta = ""  # Buffer para acumular respostas

def temporizador_base():
    """Função chamada quando o temporizador da base expira no Go-Back-N"""
    global timer, tamanho_janela, finalizou
    
    if finalizou:
        return
        
    print(f"[TIMEOUT] Retransmissão por timeout após 10s - Base {base}! Hora: {time.strftime('%H:%M:%S')}")

    with lock:
        # Verifica se ainda há pacotes não confirmados
        if base > qtd_pacotes:
            print("[DEBUG] Todos os pacotes já foram confirmados, cancelando timer")
            return
            
        # Timeout - reduzir o tamanho da janela
        tamanho_janela_antigo = tamanho_janela
        tamanho_janela = max(tamanho_janela // 2, tamanho_janela_min)
        if tamanho_janela_antigo != tamanho_janela:
            print(f"[JANELA] Reduzida de {tamanho_janela_antigo} para {tamanho_janela} após timeout")
        
        # No Go-Back-N, reenvia apenas os pacotes a partir da base (não confirmados)
        print(f"[DEBUG] Reenviando pacotes não confirmados a partir da base {base}")
        for i in range(base, qtd_pacotes + 1):
            if i not in pacotes_confirmados:
                enviar_pacote_sem_timer(i, pacotes[i-1])
            else:
                print(f"[DEBUG] Pacote {i} já confirmado, pulando")
        
        # Reinicia o temporizador se ainda há pacotes não confirmados
        if base <= qtd_pacotes and not finalizou:
            timer = threading.Timer(10.0, temporizador_base)
            timer.start()

def iniciar_timer_base():
    """Inicia ou reinicia o temporizador da base para Go-Back-N"""
    global timer
    
    if timer is not None:
        timer.cancel()
    
    # Só inicia timer se há pacotes não confirmados e não finalizou
    if base <= qtd_pacotes and not finalizou:
        timeout_inicial = 15.0 if not pacotes_confirmados else 10.0
        timer = threading.Timer(timeout_inicial, temporizador_base)
        timer.start()

def enviar_pacote_inicial(idx, pacote):
    """Envia um pacote inicial (usado no modo lote)"""
    # Simulação de perda
    if simular_perdas and random.random() < prob_perda:
        print(f"[SIMULAÇÃO] Pacote {idx} NÃO enviado (simulação de PERDA) - Retransmissão por timeout em ~10s.")
        return False

    # Simulação de erro
    if simular_erros and random.random() < prob_erro:
        checksum = (calcular_checksum(pacote) + 1) % 256
        print(f"[SIMULAÇÃO] Pacote {idx} enviado com CHECKSUM ERRADO - Retransmissão imediata por NACK.")
    else:
        checksum = calcular_checksum(pacote)

    pacote_enviado = f"{checksum:03d}|{idx:03d}|{pacote}"
    try:
        s.sendall(pacote_enviado.encode())
        print(f"Pacote {idx} enviado: '{pacote_enviado}'")
        return True
    except Exception as e:
        print(f"Erro ao enviar pacote {idx}: {e}")
        return False

def enviar_pacote_sem_timer(idx, pacote):
    """Envia um pacote sem gerenciar temporizadores (usado em retransmissões)"""
    # NÃO simula erro nem perda na retransmissão
    checksum = calcular_checksum(pacote)
        
    pacote_enviado = f"{checksum:03d}|{idx:03d}|{pacote}"
    try:
        s.sendall(pacote_enviado.encode())
        print(f"Pacote {idx} reenviado: '{pacote_enviado}'")
    except Exception as e:
        print(f"Erro ao reenviar pacote {idx}: {e}")

def cancelar_timers():
    """Cancela todos os temporizadores ativos"""
    global timer, finalizou
    
    finalizou = True
    
    if timer is not None:
        timer.cancel()
        timer = None
    
    for t in timers.values():
        if isinstance(t, threading.Timer):
            t.cancel()
    timers.clear()

def extrair_respostas(texto):
    """Extrai respostas do buffer de forma mais robusta"""
    respostas = []
    i = 0
    while i < len(texto):
        if texto[i:].startswith("ack|"):
            # Encontrou um ACK
            j = i + 4
            while j < len(texto) and texto[j].isdigit():
                j += 1
            respostas.append(texto[i:j])
            i = j
        elif texto[i:].startswith("nack|"):
            # Encontrou um NACK
            j = i + 5
            while j < len(texto) and texto[j].isdigit():
                j += 1
            respostas.append(texto[i:j])
            i = j
        elif texto[i:].startswith("todos_pacotes_recebidos"):
            # Encontrou a mensagem final
            respostas.append("todos_pacotes_recebidos")
            i += 21
        else:
            i += 1
    return respostas

def thread_receptor():
    global base, proximo_seq, timer, tamanho_janela, finalizou, buffer_resposta
    
    print("[DEBUG] Thread receptora iniciada")
    pacotes_processados_na_thread = set()  # Para evitar processar a mesma resposta múltiplas vezes
    
    while not finalizou and base <= qtd_pacotes:
        try:
            resposta_bytes = s.recv(1024)
            if not resposta_bytes:
                print("[DEBUG] Conexão fechada pelo servidor.")
                break
            
            resposta = resposta_bytes.decode()
            print(f"[DEBUG] Resposta recebida: '{resposta}'")
            
            # Adiciona ao buffer
            buffer_resposta += resposta
            
            # Extrai respostas completas do buffer
            respostas = extrair_respostas(buffer_resposta)
            
            # Remove as respostas processadas do buffer
            for resp in respostas:
                buffer_resposta = buffer_resposta.replace(resp, "", 1)
            
            for resp in respostas:
                if not resp.strip():
                    continue

                # Cria uma chave única para evitar processar a mesma resposta múltiplas vezes
                chave_resposta = f"{resp}_{time.time()}"
                if chave_resposta in pacotes_processados_na_thread:
                    continue
                pacotes_processados_na_thread.add(chave_resposta)

                if resp.startswith("ack|"):
                    try:
                        numero_pacote = int(resp.split("|")[1])
                        
                        if modo_operacao == 1 and modo_envio == 2:
                            print(f"[ACK] Pacote {numero_pacote} confirmado (e todos anteriores implicitamente).")
                        else:
                            print(f"[ACK] Pacote {numero_pacote} confirmado.")
                        
                        # ACK bem-sucedido - aumentar janela em 1
                        tamanho_janela_antigo = tamanho_janela
                        tamanho_janela += 1
                        print(f"[JANELA] Aumentada de {tamanho_janela_antigo} para {tamanho_janela}")
                        
                    except Exception as e:
                        print(f"Erro ao processar ACK: {e}")
                        continue

                    with lock:
                        if modo_operacao == 1:  # Go-Back-N
                            # No Go-Back-N lote, um ACK confirma todos os pacotes até aquele número
                            if numero_pacote >= base:
                                if numero_pacote > base:
                                    print(f"[DEBUG] ACK {numero_pacote} confirma pacotes {base} até {numero_pacote} implicitamente")
                                
                                # Confirma todos os pacotes até numero_pacote
                                for i in range(base, numero_pacote + 1):
                                    pacotes_confirmados.add(i)
                                
                                # Atualiza a base para o próximo pacote não confirmado
                                base = numero_pacote + 1
                                print(f"[DEBUG] Nova base: {base}")

                                # Cancela o timer da base se todos foram confirmados
                                if base > qtd_pacotes:
                                    if timer is not None:
                                        timer.cancel()
                                        timer = None
                                    print(f"[DEBUG] Todos os pacotes confirmados, timer cancelado")
                                    finalizou = True
                                    return
                                else:
                                    # Reinicia o timer se ainda há pacotes pendentes
                                    iniciar_timer_base()
                        
                        else:  # Repetição Seletiva
                            pacotes_confirmados.add(numero_pacote)
                            
                            # Cancela o timer específico do pacote confirmado
                            if numero_pacote in timers:
                                timers[numero_pacote].cancel()
                                del timers[numero_pacote]
                                print(f"[DEBUG] Timer cancelado para pacote {numero_pacote}")
                            
                            # Atualiza a base para o próximo pacote não confirmado
                            while base in pacotes_confirmados and base <= qtd_pacotes:
                                base += 1
                            
                            print(f"[DEBUG] Nova base: {base}")
                            
                            # Se todos foram confirmados
                            if base > qtd_pacotes:
                                cancelar_timers()
                                finalizou = True
                                return

                elif resp.startswith("nack|"):
                    try:
                        numero_pacote = int(resp.split("|")[1])
                        print(f"[NACK] Retransmissão IMEDIATA por falha de integridade - Pacote {numero_pacote}")

                        # Reduzir janela pela metade
                        tamanho_janela_antigo = tamanho_janela
                        tamanho_janela = max(tamanho_janela // 2, tamanho_janela_min)
                        if tamanho_janela != tamanho_janela_antigo:
                            print(f"[JANELA] Reduzida de {tamanho_janela_antigo} para {tamanho_janela} após NACK")

                        with lock:
                            if modo_operacao == 1:  # Go-Back-N
                                # CORREÇÃO: No Go-Back-N, NÃO atualiza a base após NACK
                                # A base só muda quando recebemos ACK
                                print(f"[DEBUG] NACK recebido para pacote {numero_pacote}, base permanece: {base}")
                                
                                # Cancela timer atual
                                if timer is not None:
                                    timer.cancel()
                                    timer = None
                                
                                # Reenvia a partir da base atual até o final
                                print(f"[DEBUG] Reenviando a partir da base {base} até pacote {qtd_pacotes}")
                                for i in range(base, qtd_pacotes + 1):
                                    enviar_pacote_sem_timer(i, pacotes[i-1])
                                
                                # Reinicia o timer da base
                                iniciar_timer_base()
                            
                            else:  # Repetição Seletiva
                                # Reenvia apenas o pacote com erro
                                if numero_pacote <= qtd_pacotes:
                                    enviar_pacote_sem_timer(numero_pacote, pacotes[numero_pacote-1])

                    except Exception as e:
                        print(f"Erro ao processar NACK: {e}")

                elif resp.strip() == "todos_pacotes_recebidos":
                    print("\nServidor confirmou recebimento de todos os pacotes.")
                    print("[DEBUG] Thread receptora finalizando normalmente")
                    finalizou = True
                    return

        except socket.timeout:
            print("[DEBUG] Timeout na thread receptora, continuando...")
            continue
        except Exception as e:
            if finalizou:
                print("[DEBUG] Socket fechado, thread receptora finalizando.")
                break
            else:
                print(f"Erro na thread receptora: {e}")
                break
    
    print("[DEBUG] Thread receptora finalizou")

# Resto do código permanece igual...
try:
    s.connect((HOST, PORT))
    print(f"\nConectado ao servidor {HOST}:{PORT}")
    
    # Envia handshake
    modo_str = "Go-Back-N" if modo_operacao == 1 else "Repetição Seletiva"
    envio_str = "Individual" if modo_envio == 1 else "Lote"
    simulacao_str = ["Normal", "Falha de Integridade", "Perda de Pacote"][tipo_simulacao - 1]
    
    print(f"\nConfiguração: {modo_str} + {envio_str} + {simulacao_str}")
    print(f"Janela inicial: {tamanho_janela}")
    
    mensagem_handshake = f"modo={modo_operacao},limite máximo={limite_max}, envio={modo_envio},qtd_pacotes={qtd_pacotes},janela={tamanho_janela}"
    s.sendall(mensagem_handshake.encode())
    
    resposta = s.recv(1024).decode()
    
    if resposta == "ack_handshake":
        print("Handshake concluído com sucesso.\n")
        
        if modo_envio == 1:  # Modo Individual
            print("Enviando em modo INDIVIDUAL...\n")
            
            idx = 1
            max_tentativas_por_pacote = 5
            
            while idx <= len(pacotes):
                pacote = pacotes[idx-1]
                
                # Envia o pacote
                enviado = enviar_pacote_inicial(idx, pacote)
                if not enviado:
                    print(f"[RECUPERAÇÃO] Tentando reenviar pacote {idx} após simulação de perda...")
                    sleep(0.5)
                    enviar_pacote_sem_timer(idx, pacote)
                
                tentativas = 0
                pacote_confirmado = False
                
                while tentativas < max_tentativas_por_pacote and not pacote_confirmado:
                    try:
                        resposta = s.recv(1024).decode()
                        
                        respostas = resposta.replace("ack|", "\nack|").replace("nack|", "\nnack|").split("\n")
                        for resp in respostas:
                            if not resp:
                                continue
                                
                            if resp.startswith("ack|"):
                                try:
                                    numero_pacote = int(resp.split("|")[1])
                                    print(f"[ACK] Pacote {numero_pacote} confirmado.")
                                    
                                    if numero_pacote == idx:
                                        pacote_confirmado = True
                                        # Aumentar janela em 1
                                        tamanho_janela_antigo = tamanho_janela
                                        tamanho_janela += 1
                                        print(f"[JANELA] Aumentada de {tamanho_janela_antigo} para {tamanho_janela}")
                                        
                                        pacotes_confirmados.add(idx)
                                        break
                                    
                                except Exception as e:
                                    print(f"Erro ao processar ACK: {e}")
                                    continue
                                    
                            elif resp.startswith("nack|"):
                                try:
                                    numero_pacote = int(resp.split("|")[1])
                                    print(f"[NACK] Retransmissão IMEDIATA por falha de integridade - Pacote {numero_pacote}")
                                    
                                    if numero_pacote == idx:
                                        # Reduzir janela pela metade
                                        tamanho_janela_antigo = tamanho_janela
                                        tamanho_janela = max(tamanho_janela // 2, tamanho_janela_min)
                                        print(f"[JANELA] Reduzida de {tamanho_janela_antigo} para {tamanho_janela} após NACK")
                                        
                                        # Re-envia o pacote
                                        enviar_pacote_sem_timer(idx, pacotes[idx-1])
                                        tentativas += 1
                                except Exception as e:
                                    print(f"Erro ao processar NACK: {e}")
                                    continue
                                    
                        if pacote_confirmado:
                            break
                            
                    except socket.timeout:
                        tentativas += 1
                        print(f"[TIMEOUT] Tentativa {tentativas} aguardando ACK/NACK para pacote {idx} - Retransmissão por timeout...")
                        if tentativas < max_tentativas_por_pacote:
                            # Reduzir janela após timeout
                            tamanho_janela_antigo = tamanho_janela
                            tamanho_janela = max(tamanho_janela // 2, tamanho_janela_min)
                            if tamanho_janela_antigo != tamanho_janela:
                                print(f"[JANELA] Reduzida de {tamanho_janela_antigo} para {tamanho_janela} após timeout")
                            
                            enviar_pacote_sem_timer(idx, pacote)
                
                if not pacote_confirmado:
                    print(f"[ERRO] Pacote {idx} falhou após {max_tentativas_por_pacote} tentativas.")
                    if idx < len(pacotes):
                        resposta_usuario = input(f"Deseja continuar com o próximo pacote? (s/n): ").strip().lower()
                        if resposta_usuario != 's':
                            print("Envio interrompido pelo usuário.")
                            break
                
                if pacote_confirmado or tentativas >= max_tentativas_por_pacote:
                    idx += 1
                    if idx <= len(pacotes):
                        sleep(0.5)

        else:  # Modo Lote
            print(f"Enviando em modo LOTE com janela inicial={tamanho_janela}...\n")
            
            print("Enviando todos os pacotes de uma vez...")
            # Envia todos os pacotes sem aguardar ACKs
            pelo_menos_um_enviado = False
            for i in range(1, qtd_pacotes + 1):
                enviado = enviar_pacote_inicial(i, pacotes[i-1])
                if enviado:
                    pelo_menos_um_enviado = True
            
            # Inicia timers conforme o modo de operação
            if modo_operacao == 1:  # Go-Back-N
                if pelo_menos_um_enviado:
                    iniciar_timer_base()
            else:  # Repetição Seletiva
                # Na Repetição Seletiva, cria timers para TODOS os pacotes
                # (mesmo os perdidos), pois cada um precisa de timeout individual
                for i in range(1, qtd_pacotes + 1):
                    def timeout_seletivo(idx=i):
                        if finalizou:
                            return
                        with lock:
                            if idx not in pacotes_confirmados:
                                print(f"[TIMEOUT] Retransmissão por timeout após 15s - Pacote {idx}")
                                global tamanho_janela
                                tamanho_janela_antigo = tamanho_janela
                                tamanho_janela = max(tamanho_janela // 2, tamanho_janela_min)
                                if tamanho_janela_antigo != tamanho_janela:
                                    print(f"[JANELA] Reduzida de {tamanho_janela_antigo} para {tamanho_janela} após timeout")
                                
                                enviar_pacote_sem_timer(idx, pacotes[idx-1])
                                
                                # Reinicia o timer para este pacote
                                if not finalizou:
                                    timer_individual = threading.Timer(15.0, timeout_seletivo)
                                    timer_individual.start()
                                    timers[idx] = timer_individual
                    
                    # Cria timer inicial para cada pacote
                    timer_inicial = threading.Timer(15.0, timeout_seletivo)
                    timer_inicial.start()
                    timers[i] = timer_inicial
            
            # Inicia thread para receber ACKs/NACKs
            receptor = threading.Thread(target=thread_receptor)
            receptor.daemon = True
            receptor.start()
            
            # Aguarda até que todos os pacotes sejam confirmados ou timeout
            timeout_counter = 0
            while base <= qtd_pacotes and not finalizou:
                sleep(0.1)
                timeout_counter += 1
                # Timeout máximo de 60 segundos
                if timeout_counter > 600:
                    print("[ERRO] Timeout máximo atingido, finalizando...")
                    break

        print("\nAguardando últimas confirmações...")
        sleep(3)
    
        if len(pacotes_confirmados) == qtd_pacotes:
            print("\nTodos os pacotes foram enviados e confirmados.")
        else:
            print(f"\nProcesso finalizado. Pacotes confirmados: {len(pacotes_confirmados)}/{qtd_pacotes}")
            
    elif resposta == "nack_handshake":
        print("Servidor rejeitou o handshake. Verifique os parâmetros e tente novamente.")
    else:
        print(f"Resposta inesperada do servidor: {resposta}")

except Exception as e:
    print(f"Ocorreu um erro: {e}")
finally:
    finalizou = True
    cancelar_timers()
    s.close()
    print("Conexão fechada.")