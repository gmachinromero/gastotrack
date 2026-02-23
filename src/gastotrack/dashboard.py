"""
Dashboard de estadísticas para GastoTrack usando Streamlit.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
from collections import defaultdict

from gastotrack.bd import BaseDatos
from gastotrack.config import Config


def cargar_datos() -> tuple[list, dict]:
    """
    Carga todos los tickets de la base de datos.

    Returns:
        Tupla con (lista de tickets, estadísticas básicas)
    """
    with BaseDatos() as bd:
        tickets = bd.obtener_todos_tickets()
        stats = bd.obtener_estadisticas_basicas()
    return tickets, stats


def preparar_datos_mensuales(tickets: list) -> pd.DataFrame:
    """
    Prepara datos agregados por mes.

    Args:
        tickets: Lista de objetos Ticket

    Returns:
        DataFrame con columnas: año_mes, total, num_tickets
    """
    datos_mensuales = defaultdict(lambda: {'total': 0.0, 'num_tickets': 0})

    for ticket in tickets:
        # Extraer año-mes
        fecha = datetime.strptime(ticket.fecha, '%Y-%m-%d')
        año_mes = fecha.strftime('%Y-%m')

        datos_mensuales[año_mes]['total'] += ticket.total_final()
        datos_mensuales[año_mes]['num_tickets'] += 1

    # Convertir a DataFrame
    df = pd.DataFrame([
        {
            'año_mes': año_mes,
            'total': datos['total'],
            'num_tickets': datos['num_tickets']
        }
        for año_mes, datos in sorted(datos_mensuales.items())
    ])

    return df


def preparar_datos_categoria(tickets: list, categoria_filtro: str = None) -> pd.DataFrame:
    """
    Prepara datos de detalles por categoría.

    Args:
        tickets: Lista de objetos Ticket
        categoria_filtro: Categoría para filtrar (None = todas)

    Returns:
        DataFrame con detalles de productos
    """
    datos = []

    for ticket in tickets:
        for detalle in ticket.detalles:
            if detalle.eliminado:
                continue

            if categoria_filtro and detalle.categoria != categoria_filtro:
                continue

            datos.append({
                'fecha': ticket.fecha,
                'supermercado': ticket.supermercado,
                'descripcion': detalle.descripcion_original,
                'categoria': detalle.categoria,
                'precio': detalle.precio_final(),
            })

    return pd.DataFrame(datos)


def vista_resumen(tickets: list, stats: dict):
    """Vista 1: Resumen general."""
    st.header("📊 Resumen General")

    # Métricas principales
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("💰 Total Gastado", f"{stats['total_gastado']:.2f}€")

    with col2:
        st.metric("🧾 Número de Tickets", stats['num_tickets'])

    with col3:
        if stats['num_tickets'] > 0:
            media_ticket = stats['total_gastado'] / stats['num_tickets']
            st.metric("📈 Media por Ticket", f"{media_ticket:.2f}€")
        else:
            st.metric("📈 Media por Ticket", "0.00€")

    # Calcular media mensual
    if tickets:
        df_mensual = preparar_datos_mensuales(tickets)
        if not df_mensual.empty:
            media_mensual = df_mensual['total'].mean()

            # Último mes
            ultimo_mes = df_mensual.iloc[-1]
            diferencia = ultimo_mes['total'] - media_mensual
            porcentaje = (diferencia / media_mensual * 100) if media_mensual > 0 else 0

            st.subheader("📅 Comparativa Mensual")
            col1, col2 = st.columns(2)

            with col1:
                st.metric("Media Mensual", f"{media_mensual:.2f}€")

            with col2:
                st.metric(
                    f"Último Mes ({ultimo_mes['año_mes']})",
                    f"{ultimo_mes['total']:.2f}€",
                    f"{diferencia:+.2f}€ ({porcentaje:+.1f}%)"
                )


def vista_evolucion(tickets: list):
    """Vista 2: Evolución temporal."""
    st.header("📈 Evolución Temporal")

    if not tickets:
        st.info("No hay datos para mostrar.")
        return

    # Filtro por categoría
    df_detalles = preparar_datos_categoria(tickets)
    categorias_disponibles = ['Todas'] + sorted(df_detalles['categoria'].unique().tolist())

    categoria_seleccionada = st.selectbox(
        "Filtrar por categoría:",
        categorias_disponibles
    )

    # Preparar datos según filtro
    if categoria_seleccionada == 'Todas':
        df_mensual = preparar_datos_mensuales(tickets)
        titulo = "Gasto Total Mensual"
    else:
        # Filtrar tickets por categoría
        df_filtrado = preparar_datos_categoria(tickets, categoria_seleccionada)
        if df_filtrado.empty:
            st.info(f"No hay datos para la categoría '{categoria_seleccionada}'.")
            return

        # Agrupar por mes
        df_filtrado['año_mes'] = pd.to_datetime(df_filtrado['fecha']).dt.strftime('%Y-%m')
        df_mensual = df_filtrado.groupby('año_mes')['precio'].sum().reset_index()
        df_mensual.columns = ['año_mes', 'total']
        titulo = f"Gasto Mensual en {categoria_seleccionada.capitalize()}"

    # Gráfico de línea
    fig = px.line(
        df_mensual,
        x='año_mes',
        y='total',
        title=titulo,
        labels={'año_mes': 'Mes', 'total': 'Gasto (€)'},
        markers=True
    )

    fig.update_layout(
        xaxis_title="Mes",
        yaxis_title="Gasto (€)",
        hovermode='x unified'
    )

    st.plotly_chart(fig, use_container_width=True)

    # Tabla de datos
    with st.expander("Ver datos detallados"):
        st.dataframe(df_mensual, use_container_width=True)


def vista_distribucion(stats: dict):
    """Vista 3: Distribución por categoría y supermercado."""
    st.header("🏷️ Distribución de Gastos")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Por Categoría")

        if stats['gasto_por_categoria']:
            df_cat = pd.DataFrame([
                {'categoria': cat.capitalize(), 'total': total}
                for cat, total in stats['gasto_por_categoria'].items()
            ]).sort_values('total', ascending=False)

            fig_cat = px.bar(
                df_cat,
                x='categoria',
                y='total',
                title="Gasto por Categoría",
                labels={'categoria': 'Categoría', 'total': 'Gasto (€)'},
                color='total',
                color_continuous_scale='Blues'
            )

            fig_cat.update_layout(showlegend=False)
            st.plotly_chart(fig_cat, use_container_width=True)

            # Tabla
            with st.expander("Ver datos"):
                st.dataframe(df_cat, use_container_width=True)
        else:
            st.info("No hay datos de categorías.")

    with col2:
        st.subheader("Por Supermercado")

        if stats['gasto_por_supermercado']:
            df_super = pd.DataFrame([
                {'supermercado': super_nombre, 'total': total}
                for super_nombre, total in stats['gasto_por_supermercado'].items()
            ]).sort_values('total', ascending=False)

            fig_super = px.bar(
                df_super,
                x='supermercado',
                y='total',
                title="Gasto por Supermercado",
                labels={'supermercado': 'Supermercado', 'total': 'Gasto (€)'},
                color='total',
                color_continuous_scale='Greens'
            )

            fig_super.update_layout(showlegend=False)
            st.plotly_chart(fig_super, use_container_width=True)

            # Tabla
            with st.expander("Ver datos"):
                st.dataframe(df_super, use_container_width=True)
        else:
            st.info("No hay datos de supermercados.")


def main():
    """Función principal del dashboard."""
    st.set_page_config(
        page_title="GastoTrack Dashboard",
        page_icon="🧾",
        layout="wide"
    )

    st.title("🧾 GastoTrack Dashboard")
    st.markdown("---")

    # Cargar datos
    try:
        tickets, stats = cargar_datos()
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return

    if not tickets:
        st.warning("No hay tickets registrados todavía. Envía tu primer ticket al bot de Telegram.")
        return

    # Menú de navegación
    vista = st.sidebar.radio(
        "Selecciona una vista:",
        ["📊 Resumen General", "📈 Evolución Temporal", "🏷️ Distribución"]
    )

    # Mostrar vista seleccionada
    if vista == "📊 Resumen General":
        vista_resumen(tickets, stats)
    elif vista == "📈 Evolución Temporal":
        vista_evolucion(tickets)
    elif vista == "🏷️ Distribución":
        vista_distribucion(stats)

    # Footer
    st.markdown("---")
    st.caption(f"Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()
