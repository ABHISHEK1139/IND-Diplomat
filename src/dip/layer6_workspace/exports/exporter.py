import logging

logger = logging.getLogger("DIP3.Layer6.Exporter")

class MultiFormatExporter:
    """
    Supports multi-format delivery (Markdown, PDF, Word, HTML, JSON, Graph, Shared Link).
    """
    def export(self, dossier, format="pdf"):
        logger.info(f"Exporting dossier to {format}")
        return f"path/to/exported_file.{format}"
