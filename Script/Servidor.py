import socket
from datetime import datetime
from time import sleep

def calcular_checksum(pacote):
    return sum(ord(char) for char in pacote) % 256

HOST = 'localhost'
PORT = 50000

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen()
    print(f"Servidor esperando conexão do cliente em {HOST}:{PORT}...")

    try:
        while True:
            conn, ender = s.accept()
            processar_comunicacao(conn, ender)
            conn.close()
            print("Conexão encerrada com o cliente. Aguardando nova conexão...")
    except KeyboardInterrupt:
        print("\nServidor encerrado pelo usuário.")
    except Exception as e:
        print(f"Erro no servidor: {e}")
    finally:
        s.close()
        print("Servidor encerrado.")

def processar_comunicacao(conn, ender):
    print('Conectado em ', ender)
    
    while True:
        try:
            print("\nAguardando novo handshake do cliente...")
            handshake = conn.recv(1024).decode()
            
            if not handshake:
                print("Cliente desconectou.")
                break
                
            print(f"Handshake recebido: {handshake}")
            
            partes = handshake.split(',')
            if len(partes) < 4:
                conn.sendall("nack_handshake".encode())
                print("Handshake inválido. Aguardando novo handshake.")
                continue
    
            try:
                modo_operacao = int(partes[0].split('=')[1])
                tamanho_max = int(partes[1].split('=')[1])
                modo_envio = int(partes[2].split('=')[1])
                qtd_pacotes = int(partes[3].split('=')[1])
                
                tamanho_janela = 1
                if len(partes) > 4 and partes[4].startswith("janela="):
                    tamanho_janela = int(partes[4].split('=')[1])
            except (ValueError, IndexError):
                conn.sendall("nack_handshake".encode())
                print("Erro no parsing do handshake. Aguardando novo handshake.")
                continue
    
            print(f"Modo de operação: {'Go-Back-N' if modo_operacao == 1 else 'Repetição Seletiva'}")
            print(f"Tamanho máximo: {tamanho_max}, Modo de envio: {'Individual' if modo_envio == 1 else 'Lote'}")
            print(f"Quantidade de pacotes: {qtd_pacotes}, Tamanho da janela: {tamanho_janela}")
            conn.sendall("ack_handshake".encode())
    
            print("\nAguardando pacotes...\n")
            
            buffer_completo = ""
            pacotes_processados = 0
            mensagem_completa = ""
            
            # Para armazenar pacotes fora de ordem (para repetição seletiva)
            pacotes_armazenados = {}
            proximo_esperado = 1
            
            # Variáveis para controle de ACKs no Go-Back-N em lote
            ultimo_pacote_continuo = 0  # Último pacote recebido em sequência contínua
            tempo_ultimo_pacote = datetime.now()
            pacotes_recebidos_lote = []  # Buffer para acumular pacotes em lote
    
            while pacotes_processados < qtd_pacotes:
                dados = conn.recv(1024).decode()
                
                if not dados:
                    print("Cliente desconectou durante a transmissão.")
                    return
                    
                buffer_completo += dados
                
                while '|' in buffer_completo and pacotes_processados < qtd_pacotes:
                    primeiro_separador = buffer_completo.find('|')
                    if primeiro_separador < 3:
                        break
                        
                    try:
                        checksum_recebido = int(buffer_completo[:primeiro_separador])
                    except ValueError:
                        print(f"Erro ao extrair checksum: '{buffer_completo[:primeiro_separador]}'")
                        buffer_completo = buffer_completo[primeiro_separador+1:]
                        continue
                        
                    resto = buffer_completo[primeiro_separador+1:]
                    segundo_separador = resto.find('|')
                    if segundo_separador == -1:
                        break
                        
                    try:
                        numero_sequencia = int(resto[:segundo_separador])
                    except ValueError:
                        print(f"Erro ao extrair número de sequência: '{resto[:segundo_separador]}'")
                        buffer_completo = buffer_completo[primeiro_separador+1:]
                        continue
                        
                    conteudo = resto[segundo_separador+1:]
                    if len(conteudo) < 1:
                        break
                        
                    if len(conteudo) <= 3:
                        conteudo_pacote = conteudo
                        buffer_completo = ""
                    else:
                        conteudo_pacote = conteudo[:3]
                        buffer_completo = conteudo[3:]
                    
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
                                # Pacote em ordem - aceita
                                mensagem_completa += conteudo_pacote
                                pacotes_processados += 1
                                proximo_esperado += 1
                                ultimo_pacote_continuo = numero_sequencia
                                
                                if modo_envio == 1:  # Individual
                                    sleep(0.05)
                                    conn.sendall(f"ack|{numero_sequencia}".encode())
                                    print(f"- ACK enviado para pacote {numero_sequencia}")
                                else:  # Lote
                                    # Em lote Go-Back-N, acumula pacotes mas não envia ACK imediatamente
                                    pacotes_recebidos_lote.append(numero_sequencia)
                                    print(f"- Pacote {numero_sequencia} aceito e armazenado (último contínuo: {ultimo_pacote_continuo})")
                                
                            else:
                                # Pacote fora de ordem - DESCARTA em Go-Back-N
                                print(f"- Pacote {numero_sequencia} DESCARTADO (esperava {proximo_esperado})")
                                # No Go-Back-N, não processa pacotes fora de ordem
                                if modo_envio == 1:  # Individual
                                    # Reenvia ACK do último pacote aceito em sequência
                                    if ultimo_pacote_continuo > 0:
                                        sleep(0.05)
                                        conn.sendall(f"ack|{ultimo_pacote_continuo}".encode())
                                        print(f"- ACK reenviado para pacote {ultimo_pacote_continuo} (último aceito)")
                                # Em modo lote, não envia resposta imediata
                        
                        else:  # Repetição Seletiva
                            if numero_sequencia == proximo_esperado:
                                mensagem_completa += conteudo_pacote
                                pacotes_processados += 1
                                proximo_esperado += 1
                                
                                # Verifica se há pacotes armazenados que agora estão em sequência
                                while proximo_esperado in pacotes_armazenados:
                                    mensagem_completa += pacotes_armazenados[proximo_esperado]
                                    del pacotes_armazenados[proximo_esperado]
                                    pacotes_processados += 1
                                    proximo_esperado += 1
                                
                                # Na Repetição Seletiva, sempre envia ACK individual
                                sleep(0.05)
                                conn.sendall(f"ack|{numero_sequencia}".encode())
                                print(f"- ACK enviado para pacote {numero_sequencia}")
                            
                            else:
                                if numero_sequencia > proximo_esperado:
                                    # Pacote futuro - armazena
                                    pacotes_armazenados[numero_sequencia] = conteudo_pacote
                                    print(f"- Pacote {numero_sequencia} armazenado (esperava {proximo_esperado})")
                                    
                                    # Envia ACK mesmo para pacotes fora de ordem na Repetição Seletiva
                                    sleep(0.05)
                                    conn.sendall(f"ack|{numero_sequencia}".encode())
                                    print(f"- ACK enviado para pacote {numero_sequencia} (fora de ordem)")
                                else:
                                    # Pacote duplicado
                                    print(f"- Pacote {numero_sequencia} duplicado (já processamos até {proximo_esperado-1})")
                                    sleep(0.05)
                                    conn.sendall(f"ack|{numero_sequencia}".encode())
                                    print(f"- ACK enviado para pacote {numero_sequencia} (duplicado)")
                    
                    else:
                        print("- Status: ERRO de Checksum (pacote corrompido!)")
                        sleep(0.05)
                        if modo_operacao == 1:  # Go-Back-N
                            # NACK indica para retransmitir a partir do próximo esperado
                            conn.sendall(f"nack|{proximo_esperado}".encode())
                            print(f"- NACK enviado para pacote {proximo_esperado}")
                        else:  # Repetição Seletiva
                            # NACK específico para o pacote corrompido
                            conn.sendall(f"nack|{numero_sequencia}".encode())
                            print(f"- NACK enviado para pacote {numero_sequencia}")
                    
                    print("---------------------------")
                    
                    # Atualiza tempo do último pacote para controle de lote
                    tempo_ultimo_pacote = tempo_atual
                
                # Após processar um lote de pacotes em Go-Back-N
                if modo_envio == 2 and modo_operacao == 1 and ultimo_pacote_continuo > 0:
                    # Verifica se há uma pausa natural entre blocos de pacotes
                    sleep(0.1)  # Pequena pausa para aguardar mais pacotes
                    
                    # Se não há buffer pendente, envia ACK acumulado
                    try:
                        # Tenta ler mais dados por um tempo curto
                        conn.settimeout(0.1)
                        dados_extras = conn.recv(1024).decode()
                        if dados_extras:
                            buffer_completo += dados_extras
                            conn.settimeout(None)  # Volta ao modo bloqueante
                            continue  # Volta para processar os dados extras
                    except socket.timeout:
                        # Timeout esperado - não há mais pacotes chegando
                        pass
                    
                    conn.settimeout(None)  # Volta ao modo bloqueante
                    
                    # Se há pacotes confirmados em sequência, envia ACK
                    if ultimo_pacote_continuo > 0:
                        sleep(0.05)
                        conn.sendall(f"ack|{ultimo_pacote_continuo}".encode())
                        print(f"- ACK de lote enviado para pacote {ultimo_pacote_continuo} (confirmando 1 até {ultimo_pacote_continuo})")
                        
                        # Se confirmou todos os pacotes, não precisa continuar
                        if ultimo_pacote_continuo >= qtd_pacotes:
                            pacotes_processados = qtd_pacotes
                            break
            
            # Finalização - envia confirmação de conclusão
            if modo_envio == 2:
                # Para Go-Back-N, enviar ACK final se houver pendente
                if modo_operacao == 1 and ultimo_pacote_continuo > 0 and ultimo_pacote_continuo < qtd_pacotes:
                    sleep(0.05)
                    conn.sendall(f"ack|{ultimo_pacote_continuo}".encode())
                    print(f"- ACK de lote final enviado para pacote {ultimo_pacote_continuo}")
                
                # Pequena pausa antes de enviar confirmação final
                sleep(0.1)
                conn.sendall("todos_pacotes_recebidos".encode())
                print("- Mensagem 'todos_pacotes_recebidos' enviada")
        
            print(f"\nMensagem completa reconstruída: '{mensagem_completa}'")
            print("\nTransmissão concluída. Aguardando nova transmissão do cliente...")
            
        except Exception as e:
            print(f"Erro ao processar: {e}")
            break

if __name__ == "__main__":
    main()