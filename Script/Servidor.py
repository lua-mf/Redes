import socket
from datetime import datetime
from time import sleep

def calcular_checksum(pacote):
    return sum(ord(char) for char in pacote) % 256

HOST = 'localhost'
PORT = 50000

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen()
print(f"Servidor esperando conexão do cliente em {HOST}:{PORT}...")
conn, ender = s.accept()
print('Conectado em ', ender)

handshake = conn.recv(1024).decode()
print(f"Handshake recebido: {handshake}")

try:
    partes = handshake.split(',')
    
    # Verificação de integridade do handshake
    if len(partes) < 4:
        conn.sendall("nack_handshake".encode())
        conn.close()
        print("Handshake inválido. Conexão encerrada.")
        exit()

    try:
        modo_operacao = int(partes[0].split('=')[1])
        tamanho_max = int(partes[1].split('=')[1])
        modo_envio = int(partes[2].split('=')[1])
        qtd_pacotes = int(partes[3].split('=')[1])
        
        # Verificar se há tamanho da janela informado (para modo em lote)
        tamanho_janela = 1
        if len(partes) > 4 and partes[4].startswith("janela="):
            tamanho_janela = int(partes[4].split('=')[1])
    except (ValueError, IndexError):
        conn.sendall("nack_handshake".encode())
        conn.close()
        print("Erro no parsing do handshake. Conexão encerrada.")
        exit()

    print(f"Modo de operação: {'Go-Back-N' if modo_operacao == 1 else 'Repetição Seletiva'}")
    print(f"Tamanho máximo: {tamanho_max}, Modo de envio: {'Individual' if modo_envio == 1 else 'Lote'}")
    print(f"Quantidade de pacotes: {qtd_pacotes}, Tamanho da janela: {tamanho_janela}")
    conn.sendall("ack_handshake".encode())

    print("\nAguardando pacotes...\n")
    
    buffer_completo = ""
    pacotes_processados = 0
    mensagem_completa = ""
    ultimo_ack_enviado = 0  # Para Go-Back-N: última confirmação enviada
    
    # Para armazenar pacotes fora de ordem (para repetição seletiva)
    pacotes_armazenados = {}
    proximo_esperado = 1  # Próximo número de sequência esperado
    
    # Variáveis para controle de ACKs no Go-Back-N em lote
    pacotes_lote_gbn = []  # Lista para armazenar pacotes recebidos em lote no Go-Back-N
    tempo_ultimo_pacote = datetime.now()  # Para controle de tempo entre pacotes
    enviar_ack_pendente = False  # Flag para indicar que há ACK pendente para enviar

    while pacotes_processados < qtd_pacotes:
        dados = conn.recv(1024).decode()
        
        if not dados:
            break
            
        buffer_completo += dados
        
        while '|' in buffer_completo and pacotes_processados < qtd_pacotes:
            # Procura o primeiro separador para o checksum
            primeiro_separador = buffer_completo.find('|')
            if primeiro_separador < 3:  # checksum tem pelo menos 3 dígitos
                break
                
            try:
                checksum_recebido = int(buffer_completo[:primeiro_separador])
            except ValueError:
                print(f"Erro ao extrair checksum: '{buffer_completo[:primeiro_separador]}'")
                buffer_completo = buffer_completo[primeiro_separador+1:]
                continue
                
            # Procura o segundo separador para o número de sequência
            resto = buffer_completo[primeiro_separador+1:]
            segundo_separador = resto.find('|')
            if segundo_separador == -1:
                break  # Não encontrou o segundo separador
                
            try:
                numero_sequencia = int(resto[:segundo_separador])
            except ValueError:
                print(f"Erro ao extrair número de sequência: '{resto[:segundo_separador]}'")
                buffer_completo = buffer_completo[primeiro_separador+1:]
                continue
                
            # Extrair o conteúdo do pacote
            conteudo = resto[segundo_separador+1:]
            if len(conteudo) < 1:  # Precisamos de pelo menos um caractere
                break
                
            # Se o conteúdo for menor que o tamanho máximo, pegamos só o que temos
            # (o último pacote pode ser menor)
            if len(conteudo) <= tamanho_max:
                conteudo_pacote = conteudo
                buffer_completo = ""
            else:
                conteudo_pacote = conteudo[:tamanho_max]
                buffer_completo = conteudo[tamanho_max:]
            
            checksum_calculado = calcular_checksum(conteudo_pacote)
            
            horario = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            tempo_atual = datetime.now()
            
            print(f"Pacote recebido:")
            print(f"- Conteúdo: '{conteudo_pacote}'")
            print(f"- Número de sequência: {numero_sequencia}")
            print(f"- Tamanho: {len(conteudo_pacote)}")
            print(f"- Horário: {horario}")
            print(f"- Checksum recebido: {checksum_recebido}")
            print(f"- Checksum calculado: {checksum_calculado}")
            
            if checksum_recebido == checksum_calculado:
                print("- Status: Checksum OK!")
                
                if modo_operacao == 1:  # Go-Back-N
                    if numero_sequencia == proximo_esperado:
                        # Pacote na ordem correta
                        mensagem_completa += conteudo_pacote
                        pacotes_processados += 1
                        ultimo_ack_enviado = numero_sequencia  # Atualiza o último ACK
                        proximo_esperado += 1
                        
                        # Adiciona à lista de pacotes em lote
                        pacotes_lote_gbn.append(numero_sequencia)
                        
                        # Comportamento diferente baseado no modo de envio
                        if modo_envio == 1:  # Individual
                            # No modo individual, enviamos ACK imediatamente
                            sleep(0.05)  # Pequena pausa para evitar respostas misturadas
                            conn.sendall(f"ack|{ultimo_ack_enviado}".encode())
                            print(f"- ACK enviado para pacote {ultimo_ack_enviado}")
                        else:  # Lote
                            # No modo Lote, marcamos que há ACK pendente
                            enviar_ack_pendente = True
                        
                    else:
                        # Pacote fora de ordem - descarta no Go-Back-N
                        print(f"- Pacote fora de ordem (esperava {proximo_esperado}, recebeu {numero_sequencia})")
                        
                        # Enviamos ACK do último pacote recebido corretamente
                        sleep(0.05)  # Pequena pausa para evitar respostas misturadas
                        conn.sendall(f"ack|{ultimo_ack_enviado}".encode())
                        print(f"- ACK enviado para pacote {ultimo_ack_enviado} (fora de ordem)")
                
                else:  # Repetição Seletiva
                    if numero_sequencia == proximo_esperado:
                        # Pacote na ordem correta
                        mensagem_completa += conteudo_pacote
                        pacotes_processados += 1
                        proximo_esperado += 1
                        
                        # Verifica se temos pacotes subsequentes já armazenados
                        while proximo_esperado in pacotes_armazenados:
                            mensagem_completa += pacotes_armazenados[proximo_esperado]
                            del pacotes_armazenados[proximo_esperado]
                            pacotes_processados += 1
                            proximo_esperado += 1
                        
                        # Enviamos ACK para este pacote específico
                        sleep(0.05)  # Pequena pausa para evitar respostas misturadas
                        conn.sendall(f"ack|{numero_sequencia}".encode())
                        print(f"- ACK enviado para pacote {numero_sequencia}")
                    
                    else:
                        # Pacote fora de ordem - armazena no Repetição Seletiva
                        if numero_sequencia > proximo_esperado:
                            pacotes_armazenados[numero_sequencia] = conteudo_pacote
                            print(f"- Pacote fora de ordem armazenado (esperava {proximo_esperado}, recebeu {numero_sequencia})")
                            
                            # Envia ACK mesmo para pacotes fora de ordem
                            sleep(0.05)  # Pequena pausa para evitar respostas misturadas
                            conn.sendall(f"ack|{numero_sequencia}".encode())
                            print(f"- ACK enviado para pacote {numero_sequencia} (fora de ordem)")
                        else:
                            # Pacote duplicado, já processado
                            print(f"- Pacote duplicado (já processamos até {proximo_esperado-1}, recebeu {numero_sequencia})")
                            sleep(0.05)  # Pequena pausa para evitar respostas misturadas
                            conn.sendall(f"ack|{numero_sequencia}".encode())
                            print(f"- ACK enviado para pacote {numero_sequencia} (duplicado)")
            
            else:
                print("- Status: ERRO de Checksum (pacote corrompido!)")
                # Enviamos NACK conforme o modo
                sleep(0.05)  # Pequena pausa para evitar respostas misturadas
                if modo_operacao == 1:  # Go-Back-N
                    conn.sendall(f"nack|{proximo_esperado}".encode())
                    print(f"- NACK enviado para pacote {proximo_esperado}")
                else:  # Repetição Seletiva
                    conn.sendall(f"nack|{numero_sequencia}".encode())
                    print(f"- NACK enviado para pacote {numero_sequencia}")
            
            print("---------------------------")
            
            # Verificar se é hora de enviar ACK em lote (passou tempo suficiente desde o último pacote)
            if modo_envio == 2:  # Apenas no modo lote
                intervalo = (tempo_atual - tempo_ultimo_pacote).total_seconds()
                tempo_ultimo_pacote = tempo_atual
                
                # Se já se passou tempo suficiente desde o último pacote recebido ou se é o último pacote esperado
                if (modo_operacao == 1 and enviar_ack_pendente and 
                    (intervalo > 0.1 or pacotes_processados >= qtd_pacotes)):
                    if pacotes_lote_gbn:
                        # Enviamos ACK apenas para o último pacote do lote
                        ultimo_pacote_lote = max(pacotes_lote_gbn)
                        sleep(0.05)  # Pequena pausa para evitar respostas misturadas
                        conn.sendall(f"ack|{ultimo_pacote_lote}".encode())
                        print(f"- ACK de lote enviado para pacote {ultimo_pacote_lote} (confirmando pacotes {pacotes_lote_gbn})")
                        pacotes_lote_gbn = []  # Limpa a lista de pacotes em lote
                        enviar_ack_pendente = False
    
    # Após processar todos os pacotes, enviar confirmação final para modo em lote
    if modo_envio == 2:
        # Enviamos um último ACK pendente se houver
        if modo_operacao == 1 and enviar_ack_pendente and pacotes_lote_gbn:
            ultimo_pacote_lote = max(pacotes_lote_gbn)
            sleep(0.05)  # Pequena pausa para evitar respostas misturadas
            conn.sendall(f"ack|{ultimo_pacote_lote}".encode())
            print(f"- ACK de lote final enviado para pacote {ultimo_pacote_lote}")
        
        # Pequena pausa para evitar respostas misturadas
        sleep(0.05)
        conn.sendall("todos_pacotes_recebidos".encode())
        print("- Mensagem 'todos_pacotes_recebidos' enviada")
    
    print(f"\nMensagem completa reconstruída: '{mensagem_completa}'")
    
except Exception as e:
    print(f"Erro ao processar: {e}")
finally:
    conn.close()
    print("Conexão encerrada com o cliente.")