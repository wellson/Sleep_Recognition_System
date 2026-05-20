import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta

# CSV Filename
LOG_FILE = "drowsiness_events.csv"
OUTPUT_REPORT = "drowsiness_report.png"

def generate_mock_data():
    """Generates a realistic mock CSV dataset if none exists for instant beautiful visualization."""
    print("Gerando dados ficticios para criar um relatorio analitico exemplar...")
    
    start_time = datetime.now() - timedelta(minutes=45)
    
    # Pre-calculated events list to feel like a real driving session
    # (relative offset in minutes from start, event type, duration, peak val)
    mock_events = [
        (5, "YAWN", 1.8, 0.68),
        (8, "DISTRACTION", 2.0, 0.45),  # Distraction event
        (10, "YAWN", 2.1, 0.72),
        (14, "DROWSINESS", 1.6, 0.20),
        (22, "YAWN", 2.5, 0.81),
        (25, "DISTRACTION", 3.2, 0.65), # Long distraction
        (28, "DROWSINESS", 2.2, 0.18),
        (33, "YAWN", 1.9, 0.70),
        (37, "DROWSINESS", 3.4, 0.12),  # Severe drowsiness
        (42, "DROWSINESS", 4.1, 0.08),  # Extremely severe drowsiness
    ]
    
    data = []
    for offset, ev_type, dur, peak in mock_events:
        ev_time = start_time + timedelta(minutes=offset)
        data.append({
            "Timestamp": ev_time.strftime("%Y-%m-%d %H:%M:%S"),
            "Event_Type": ev_type,
            "Duration_Seconds": dur,
            "Peak_Value": peak
        })
        
    df = pd.DataFrame(data)
    df.to_csv(LOG_FILE, index=False, encoding='utf-8')
    print(f"Sucesso! Arquivo '{LOG_FILE}' criado com dados demonstrativos.")

def create_dashboard():
    # 1. Check if CSV file is present/valid, generate mock if needed
    if not os.path.exists(LOG_FILE) or os.stat(LOG_FILE).st_size == 0:
        generate_mock_data()
    else:
        # Check if CSV is just empty headers
        try:
            temp_df = pd.read_csv(LOG_FILE)
            if len(temp_df) == 0:
                generate_mock_data()
        except Exception:
            generate_mock_data()

    # 2. Read and parse data
    try:
        df = pd.read_csv(LOG_FILE)
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    except Exception as e:
        print(f"Erro ao ler o arquivo CSV: {e}")
        return

    print(f"Carregados {len(df)} eventos de fadiga para analise.")

    # Sort by time
    df = df.sort_values('Timestamp').reset_index(drop=True)
    
    # 3. Calculate Key Metrics
    drowsy_df = df[df['Event_Type'] == 'DROWSINESS']
    yawn_df = df[df['Event_Type'] == 'YAWN']
    dist_df = df[df['Event_Type'] == 'DISTRACTION']
    
    total_events = len(df)
    total_drowsy = len(drowsy_df)
    total_yawns = len(yawn_df)
    total_dist = len(dist_df)
    
    avg_drowsy_duration = drowsy_df['Duration_Seconds'].mean() if total_drowsy > 0 else 0.0
    avg_yawn_duration = yawn_df['Duration_Seconds'].mean() if total_yawns > 0 else 0.0
    avg_dist_duration = dist_df['Duration_Seconds'].mean() if total_dist > 0 else 0.0
    
    total_danger_time = (drowsy_df['Duration_Seconds'].sum() if total_drowsy > 0 else 0.0) + \
                        (dist_df['Duration_Seconds'].sum() if total_dist > 0 else 0.0)
    
    # 4. Set Matplotlib Aesthetic Style (Sleek Dark Theme)
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['text.color'] = '#E0E0E0'
    plt.rcParams['axes.labelcolor'] = '#A0A0A0'
    plt.rcParams['xtick.color'] = '#808080'
    plt.rcParams['ytick.color'] = '#808080'
    
    fig = plt.figure(figsize=(15, 10), facecolor='#121216')
    
    # Add an overall title
    fig.suptitle('DASHBOARD DE ANALISE DE FADIGA E DISTRAÇÃO DO MOTORISTA', fontsize=18, fontweight='bold', color='#00E676', y=0.96)
    
    # Grid specification
    # Row 1: Left (Stats Cards Text), Right (Events count comparison)
    # Row 2: Event Timeline (Scatter/Line plot)
    # Row 3: Durations distribution
    gs = fig.add_gridspec(3, 2, height_ratios=[1, 1.2, 1.1])
    
    # -------------------------------------------------------------
    # SUBPLOT 1: STATS CARDS (Top Left)
    # -------------------------------------------------------------
    ax1 = fig.add_subplot(gs[0, 0], facecolor='#1E1E24')
    ax1.axis('off')
    
    # draw a subtle container box
    rect = plt.Rectangle((0, 0), 1, 1, fill=True, color='#1E1E24', transform=ax1.transAxes, clip_on=False, zorder=-1)
    ax1.add_patch(rect)
    
    stats_text = (
        f"📊 METRICAS RESUMO DA SESSÃO\n\n"
        f"• Total de Eventos Registrados: {total_events}\n"
        f"• Alertas de Sonolência (Olhos): {total_drowsy}\n"
        f"• Alertas de Bocejo (MAR): {total_yawns}\n"
        f"• Alertas de Distração (Yaw/Pitch): {total_dist}\n"
        f"• Duração Média da Sonolência: {avg_drowsy_duration:.2f}s\n"
        f"• Duração Média do Bocejo: {avg_yawn_duration:.2f}s\n"
        f"• Duração Média da Distração: {avg_dist_duration:.2f}s\n"
        f"• Tempo Total de Risco (Drowsy + Distracted): {total_danger_time:.2f}s\n"
    )
    
    # Determine general safety rating
    if total_drowsy >= 4 or total_dist >= 4 or total_danger_time > 15.0:
        safety_status = "CRÍTICO - NECESSITA DESCANSO IMEDIATO!"
        status_color = "#FF5252"
    elif total_drowsy > 1 or total_dist > 1 or total_yawns > 3:
        safety_status = "ATENÇÃO - NÍVEIS DE FADIGA/DISTRAÇÃO ELEVADOS"
        status_color = "#FFAB40"
    else:
        safety_status = "SEGURO - MOTORISTA ALERTA"
        status_color = "#00E676"
        
    ax1.text(0.05, 0.40, stats_text, fontsize=10.5, color='#E0E0E0', transform=ax1.transAxes, verticalalignment='center')
    
    ax1.text(0.05, 0.08, "AVALIAÇÃO DE RISCO:", fontsize=11, color='#A0A0A0', transform=ax1.transAxes)
    ax1.text(0.42, 0.08, safety_status, fontsize=11, fontweight='bold', color=status_color, transform=ax1.transAxes)

    # -------------------------------------------------------------
    # SUBPLOT 2: EVENT COUNTS BAR CHART (Top Right)
    # -------------------------------------------------------------
    ax2 = fig.add_subplot(gs[0, 1], facecolor='#1E1E24')
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.spines['left'].set_color('#333333')
    ax2.spines['bottom'].set_color('#333333')
    ax2.grid(axis='y', linestyle='--', alpha=0.15)
    
    categories = ['Sonolência (Olhos)', 'Bocejos (MAR)', 'Distração (Pose)']
    counts = [total_drowsy, total_yawns, total_dist]
    bar_colors = ['#FF5252', '#FFAB40', '#BD00FF']
    
    bars = ax2.bar(categories, counts, color=bar_colors, width=0.5, edgecolor='#121216', linewidth=1)
    ax2.set_ylabel('Frequência', fontsize=10, labelpad=10)
    ax2.set_title('Contagem de Ocorrências por Tipo', fontsize=12, fontweight='bold', pad=15)
    
    # Add values on top of bars
    for bar in bars:
        height = bar.get_height()
        ax2.annotate(f'{height}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    # -------------------------------------------------------------
    # SUBPLOT 3: TIMELINE OF EVENTS (Middle Row)
    # -------------------------------------------------------------
    ax3 = fig.add_subplot(gs[1, :], facecolor='#1E1E24')
    ax3.spines['top'].set_visible(False)
    ax3.spines['right'].set_visible(False)
    ax3.spines['left'].set_color('#333333')
    ax3.spines['bottom'].set_color('#333333')
    ax3.grid(True, linestyle='--', alpha=0.1)
    
    # Scatter plot
    if not df.empty:
        # Plot Drowsiness in Red
        drowsy_points = df[df['Event_Type'] == 'DROWSINESS']
        if not drowsy_points.empty:
            ax3.scatter(drowsy_points['Timestamp'], drowsy_points['Duration_Seconds'], 
                        color='#FF5252', s=120, label='Sonolência (Olhos Fechados)', 
                        alpha=0.85, edgecolors='#FFFFFF', linewidth=1)
            # Add line to show trend of drowsiness duration
            ax3.plot(drowsy_points['Timestamp'], drowsy_points['Duration_Seconds'], 
                     color='#FF5252', linestyle=':', alpha=0.4)
            
        # Plot Yawning in Orange
        yawn_points = df[df['Event_Type'] == 'YAWN']
        if not yawn_points.empty:
            ax3.scatter(yawn_points['Timestamp'], yawn_points['Duration_Seconds'], 
                        color='#FFAB40', s=120, label='Bocejos (MAR > 0.6)', 
                        alpha=0.85, edgecolors='#FFFFFF', linewidth=1)
            ax3.plot(yawn_points['Timestamp'], yawn_points['Duration_Seconds'], 
                     color='#FFAB40', linestyle=':', alpha=0.4)

        # Plot Distractions in Purple
        dist_points = df[df['Event_Type'] == 'DISTRACTION']
        if not dist_points.empty:
            ax3.scatter(dist_points['Timestamp'], dist_points['Duration_Seconds'], 
                        color='#BD00FF', s=120, label='Distração (Yaw/Pitch > 1.5s)', 
                        alpha=0.85, edgecolors='#FFFFFF', linewidth=1)
            ax3.plot(dist_points['Timestamp'], dist_points['Duration_Seconds'], 
                     color='#BD00FF', linestyle=':', alpha=0.4)

        ax3.set_title('Linha do Tempo e Duração dos Alertas', fontsize=12, fontweight='bold', pad=15)
        ax3.set_ylabel('Duração do Alerta (segundos)', fontsize=10, labelpad=10)
        ax3.legend(loc='upper left', frameon=True, facecolor='#121216', edgecolor='#333333')
        
        # Format X axis as beautiful hours
        ax3.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        # Auto rotate dates
        fig.autofmt_xdate()
    else:
        ax3.text(0.5, 0.5, "Nenhum evento registrado para exibir na linha do tempo.", 
                 ha='center', va='center', fontsize=12, color='#A0A0A0')
        
    # -------------------------------------------------------------
    # SUBPLOT 4: DURATION ANALYSIS BY EVENT TYPE (Bottom Row)
    # -------------------------------------------------------------
    ax4 = fig.add_subplot(gs[2, :], facecolor='#1E1E24')
    ax4.spines['top'].set_visible(False)
    ax4.spines['right'].set_visible(False)
    ax4.spines['left'].set_color('#333333')
    ax4.spines['bottom'].set_color('#333333')
    ax4.grid(axis='y', linestyle='--', alpha=0.1)
    
    # Horizontal line plots or area charts for severity
    if not df.empty:
        # We plot duration vs Index or Timestamp to show progressive fatigue increase
        ax4.plot(df['Timestamp'], df['Duration_Seconds'].cummax(), color='#00E676', 
                 linestyle='-', linewidth=2, label='Fadiga Máxima Acumulada (Pico)')
        ax4.fill_between(df['Timestamp'], df['Duration_Seconds'].cummax(), color='#00E676', alpha=0.08)
        
        # Plot individual event bars to show incremental density
        colors = []
        for x in df['Event_Type']:
            if x == 'DROWSINESS':
                colors.append('#FF5252')
            elif x == 'YAWN':
                colors.append('#FFAB40')
            elif x == 'DISTRACTION':
                colors.append('#BD00FF')
            else:
                colors.append('#00E676')
        ax4.bar(df['Timestamp'], df['Duration_Seconds'], width=0.0003, color=colors, alpha=0.5, label='Duração Individual')
        
        ax4.set_title('Progressão de Severidade dos Episódios ao Longo da Viagem', fontsize=12, fontweight='bold', pad=15)
        ax4.set_ylabel('Duração (s)', fontsize=10, labelpad=10)
        ax4.set_xlabel('Horário do Evento', fontsize=10, labelpad=10)
        ax4.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        ax4.legend(loc='upper left', frameon=True, facecolor='#121216', edgecolor='#333333')
    else:
        ax4.text(0.5, 0.5, "Sem dados suficientes para mapear a progressão.", 
                 ha='center', va='center', fontsize=12, color='#A0A0A0')

    # Tight layout and save
    plt.tight_layout()
    # Adjust top padding for title
    plt.subplots_adjust(top=0.88)
    
    try:
        plt.savefig(OUTPUT_REPORT, dpi=300, facecolor='#121216')
        print(f"\nDashboard gerado com sucesso!")
        print(f"Salvo em: {os.path.abspath(OUTPUT_REPORT)}")
    except Exception as e:
        print(f"Erro ao salvar a imagem do dashboard: {e}")
    finally:
        plt.close()

if __name__ == "__main__":
    create_dashboard()
