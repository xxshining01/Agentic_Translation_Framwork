import time
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.markup import escape

from .core.models import TokenState

class RichDashboard:
    def __init__(self, app):
        self.app = app
        self.layout = Layout()
        self.start_time = time.time()
        self._build_layout()

    def _build_layout(self):
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=6)
        )
        self.layout["main"].split_row(
            Layout(name="agents", ratio=2),
            Layout(name="stats", ratio=1)
        )

    def generate_header(self) -> Panel:
        elapsed = int(time.time() - self.start_time)
        return Panel(f"[bold cyan]Agentic Translation Framework (ATF)[/] - Elapsed: {elapsed}s", style="white on blue")

    def generate_agents_table(self) -> Panel:
        table = Table(show_header=True, header_style="bold magenta", expand=True)
        table.add_column("Agent Role", width=20)
        table.add_column("Current Task", style="cyan")
        
        agents = [
            self.app.analyzer,
            self.app.translator,
            self.app.editor,
            self.app.qa,
            self.app.timing,
            self.app.summarizer
        ]
        
        for agent in agents:
            task = agent.current_task
            task_text = f"[bold green]{task}[/]" if task != "IDLE" else "[dim]IDLE[/dim]"
            table.add_row(agent.agent_name, task_text)
            
        return Panel(table, title="[bold]Live Agent Activities[/]")

    def generate_stats(self) -> Panel:
        total = sum(len(b.tokens) for b in self.app.processed_batches) + len(self.app.already_translated_tokens)
        done = sum(len(b.tokens) for b in self.app.processed_batches if b.current_state in (TokenState.READY_TO_EXPORT, TokenState.ALREADY_TRANSLATED)) + len(self.app.already_translated_tokens)
        errors = sum(len(b.tokens) for b in self.app.processed_batches if b.current_state == TokenState.ERROR_CRITICAL)
        in_progress = total - done - errors
        
        stats_text = (
            f"[bold cyan]Total Tokens:[/] {total}\n"
            f"[bold green]Completed:[/] {done}\n"
            f"[bold yellow]In Progress:[/] {in_progress}\n"
            f"[bold red]Errors:[/] {errors}\n\n"
        )
        
        if total > 0:
            pct = (done / total) * 100
            stats_text += f"[bold blue]Overall Progress:[/] {pct:.1f}%"
            
        return Panel(stats_text, title="[bold]Statistics[/]")

    def generate_footer(self) -> Panel:
        # ดึงประโยคที่แปลเสร็จล่าสุด
        exported_batches = [b for b in self.app.processed_batches if b.current_state in (TokenState.READY_TO_EXPORT, TokenState.ALREADY_TRANSLATED)]
        recent_tokens = []
        if exported_batches:
            recent_tokens = exported_batches[-1].tokens[-3:]
            
        footer_text = ""
        for t in recent_tokens:
            txt = t.outputs.final_output
            short_txt = txt[:80] + "..." if txt and len(txt) > 80 else str(txt)
            short_txt = escape(short_txt)
            footer_text += f"[dim]{t.id}[/]: {short_txt}\n"
            
        if not footer_text:
            footer_text = "No outputs yet..."
            
        return Panel(footer_text.strip(), title="[bold]Latest Continuous Save[/]")

    def update(self):
        self.layout["header"].update(self.generate_header())
        self.layout["agents"].update(self.generate_agents_table())
        self.layout["stats"].update(self.generate_stats())
        self.layout["footer"].update(self.generate_footer())
