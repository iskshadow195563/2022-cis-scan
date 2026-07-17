import os
import shutil
import sys

import logging
import logging.handlers
import time
from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal, QSettings, Qt, QThread, QTimer, QSize, pyqtSlot, QMetaObject
from PyQt5.QtGui import QImageReader, QPixmap, QPainter, QImage
from PyQt5.QtWidgets import QWidget, QLabel, QApplication
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from core.language_manager import tr
from core.media_support import is_supported_media_file, list_supported_media_files, classify_media


def _default_background_dir():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_dir, "background_images")

def _default_log_dir():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_dir, "logs")


def _get_bg_logger() -> logging.Logger:
    logger = logging.getLogger("project001.background")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    try:
        log_dir = _default_log_dir()
        os.makedirs(log_dir, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "background_gif.log"),
            maxBytes=2 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    except Exception:
        logger.addHandler(logging.NullHandler())
    return logger


try:
    import psutil  # type: ignore
except Exception:
    psutil = None


def is_supported_image_file(path: str) -> bool:
    p = (path or "").strip()
    if not p:
        return False
    ext = os.path.splitext(p)[1].lower()
    return ext in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}


class BackgroundManager(QObject):
    changed = pyqtSignal()

    def __init__(self, background_dir=None, settings=None):
        super().__init__()
        self.background_dir = background_dir or _default_background_dir()
        self.settings = settings or QSettings("project-001", "WindowsSecurityAuditor")
        self._pixmap_cache = None
        self._selected_path_cache = None
        self.ensure_dir()
        self._reload_from_settings()

    def ensure_dir(self):
        os.makedirs(self.background_dir, exist_ok=True)

    def list_images(self):
        self.ensure_dir()
        try:
            names = sorted(os.listdir(self.background_dir))
        except Exception:
            return []
        out = []
        for name in names:
            p = os.path.join(self.background_dir, name)
            if os.path.isfile(p) and is_supported_image_file(p):
                out.append(p)
        return out

    def list_media(self):
        self.ensure_dir()
        return list_supported_media_files(self.background_dir)

    def selected_path(self):
        return (self._selected_path_cache or "").strip()

    def set_selected_path(self, path: str):
        p = (path or "").strip()
        if p and not os.path.isabs(p):
            p = os.path.abspath(p)
        if p == self.selected_path():
            return
        self._selected_path_cache = p
        self._pixmap_cache = None
        self.settings.setValue("ui/background_image", p)
        self.changed.emit()

    def clear(self):
        self.set_selected_path("")

    def _reload_from_settings(self):
        p = self.settings.value("ui/background_image", "") or ""
        self._selected_path_cache = str(p)

    def load_pixmap(self):
        p = self.selected_path()
        if not p:
            self._pixmap_cache = None
            return None, None
        if self._pixmap_cache is not None:
            return self._pixmap_cache, None
        if not os.path.exists(p):
            self._pixmap_cache = None
            return None, tr("bg_err_file_not_found")
        reader = QImageReader(p)
        if not reader.canRead():
            self._pixmap_cache = None
            return None, tr("bg_err_invalid_or_unsupported")
        img = reader.read()
        if img.isNull():
            self._pixmap_cache = None
            return None, tr("bg_err_decode_failed")
        self._pixmap_cache = QPixmap.fromImage(img)
        return self._pixmap_cache, None

    def add_image_from_file(self, src_path: str):
        src = (src_path or "").strip()
        if not src or not os.path.exists(src):
            return None, tr("bg_err_file_not_found")
        if not is_supported_image_file(src):
            return None, tr("bg_err_unsupported_file_type")
        self.ensure_dir()
        base = os.path.basename(src)
        dest = os.path.join(self.background_dir, base)
        if os.path.abspath(src) != os.path.abspath(dest):
            root, ext = os.path.splitext(base)
            counter = 1
            while os.path.exists(dest):
                dest = os.path.join(self.background_dir, f"{root}_{counter}{ext}")
                counter += 1
            try:
                shutil.copy2(src, dest)
            except Exception as e:
                return None, str(e)
        pixmap, err = self._try_load_pixmap_path(dest)
        if pixmap is None:
            try:
                if os.path.exists(dest) and os.path.abspath(src) != os.path.abspath(dest):
                    os.remove(dest)
            except Exception:
                pass
            return None, err or tr("bg_err_invalid_or_unsupported")
        return dest, None

    def _try_load_pixmap_path(self, path: str):
        reader = QImageReader(path)
        if not reader.canRead():
            return None, tr("bg_err_invalid_or_unsupported")
        img = reader.read()
        if img.isNull():
            return None, tr("bg_err_decode_failed")
        return QPixmap.fromImage(img), None


class _GifDecodeWorker(QObject):
    frame_ready = pyqtSignal(QImage, int, int)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(
        self,
        path: str,
        target_size: QSize,
        max_cache_frames: int = 120,
        max_cache_bytes: int = 80 * 1024 * 1024,
        min_delay_ms: int = 10,
        default_delay_ms: int = 33,
    ):
        super().__init__()
        self._path = (path or "").strip()
        self._target_size = QSize(target_size)
        self._max_cache_frames = max(0, int(max_cache_frames))
        self._max_cache_bytes = max(0, int(max_cache_bytes))
        self._min_delay_ms = max(1, int(min_delay_ms))
        self._default_delay_ms = max(1, int(default_delay_ms))
        self._timer: Optional[QTimer] = None
        self._reader: Optional[QImageReader] = None
        self._stop = False
        self._frame_index = 0
        self._cache_images = []
        self._cache_delays = []
        self._cache_bytes = 0
        self._cache_complete = False
        self._cache_playback = False
        self._cache_playback_idx = 0
        self._last_stats_t = 0.0
        self._frames_since_stats = 0
        self._logger = _get_bg_logger()

    @pyqtSlot()
    def start(self):
        if not self._path:
            self.error.emit(tr("bg_err_empty_gif_path"))
            self.finished.emit()
            return
        self._stop = False
        self._reader = QImageReader(self._path)
        self._reader.setAutoTransform(True)
        self._frame_index = 0
        self._cache_images = []
        self._cache_delays = []
        self._cache_bytes = 0
        self._cache_complete = False
        self._cache_playback = False
        self._cache_playback_idx = 0
        self._last_stats_t = time.perf_counter()
        self._frames_since_stats = 0
        if self._timer is None:
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self._tick)
        self._schedule_next(0)

    @pyqtSlot()
    def stop(self):
        self._stop = True
        if self._timer:
            try:
                self._timer.stop()
            except Exception:
                pass
        self.finished.emit()

    @pyqtSlot(QSize)
    def set_target_size(self, size: QSize):
        self._target_size = QSize(size)
        self._cache_images = []
        self._cache_delays = []
        self._cache_bytes = 0
        self._cache_complete = False
        self._cache_playback = False
        self._cache_playback_idx = 0
        self._reader = QImageReader(self._path)
        self._reader.setAutoTransform(True)
        self._frame_index = 0

    def _schedule_next(self, delay_ms: int):
        if self._stop:
            self.finished.emit()
            return
        if not self._timer:
            self.finished.emit()
            return
        delay = max(self._min_delay_ms, int(delay_ms))
        self._timer.start(delay)

    def _img_bytes(self, img: QImage) -> int:
        try:
            return int(img.sizeInBytes())
        except Exception:
            try:
                return int(img.byteCount())
            except Exception:
                return 0

    def _process_frame(self, img: QImage) -> QImage:
        if img.isNull():
            return img
        if not self._target_size.isValid() or self._target_size.isEmpty():
            return img
        scaled = img.scaled(self._target_size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        if scaled.isNull():
            return scaled
        if scaled.size() == self._target_size:
            return scaled
        x = max(0, (scaled.width() - self._target_size.width()) // 2)
        y = max(0, (scaled.height() - self._target_size.height()) // 2)
        cropped = scaled.copy(x, y, self._target_size.width(), self._target_size.height())
        return cropped if not cropped.isNull() else scaled

    def _safe_delay(self, reader: QImageReader) -> int:
        try:
            delay = int(reader.nextImageDelay())
        except Exception:
            delay = self._default_delay_ms
        if delay <= 0:
            delay = self._default_delay_ms
        return max(self._min_delay_ms, delay)

    def _emit_stats_if_needed(self):
        now = time.perf_counter()
        self._frames_since_stats += 1
        if now - self._last_stats_t < 2.0:
            return
        fps = self._frames_since_stats / max(0.001, now - self._last_stats_t)
        rss_mb = None
        if psutil is not None:
            try:
                rss_mb = psutil.Process().memory_info().rss / (1024 * 1024)
            except Exception:
                rss_mb = None
        self._logger.info(
            "gif_stats path=%s fps=%.1f cache_frames=%d cache_mb=%.1f rss_mb=%s",
            os.path.basename(self._path),
            fps,
            len(self._cache_images),
            self._cache_bytes / (1024 * 1024),
            f"{rss_mb:.1f}" if isinstance(rss_mb, (int, float)) else "n/a",
        )
        self._last_stats_t = now
        self._frames_since_stats = 0

    def _tick(self):
        if self._stop:
            self.finished.emit()
            return
        if self._cache_playback and self._cache_images:
            img = self._cache_images[self._cache_playback_idx]
            delay = self._cache_delays[self._cache_playback_idx] if self._cache_delays else self._default_delay_ms
            idx = self._frame_index
            self._frame_index += 1
            self._cache_playback_idx = (self._cache_playback_idx + 1) % len(self._cache_images)
            self.frame_ready.emit(img, delay, idx)
            self._emit_stats_if_needed()
            self._schedule_next(delay)
            return

        reader = self._reader
        if reader is None:
            self.error.emit(tr("bg_err_gif_reader_not_initialized"))
            self.finished.emit()
            return

        t0 = time.perf_counter()
        img = reader.read()
        if img.isNull():
            self.error.emit(tr("bg_err_gif_frame_decode_failed"))
            self.finished.emit()
            return
        processed = self._process_frame(img)
        delay = self._safe_delay(reader)
        idx = self._frame_index
        self._frame_index += 1
        self.frame_ready.emit(processed, delay, idx)

        if not self._cache_complete and self._max_cache_frames > 0:
            b = self._img_bytes(processed)
            if (
                len(self._cache_images) < self._max_cache_frames
                and (self._cache_bytes + b) <= self._max_cache_bytes
            ):
                self._cache_images.append(processed)
                self._cache_delays.append(delay)
                self._cache_bytes += b
            else:
                self._cache_complete = True

        ok = False
        try:
            ok = bool(reader.jumpToNextImage())
        except Exception:
            ok = False
        if not ok:
            if self._cache_images:
                self._cache_complete = True
                self._cache_playback = True
                self._cache_playback_idx = 0
                self._logger.info(
                    "gif_cache_ready path=%s frames=%d cache_mb=%.1f decode_ms=%.1f",
                    os.path.basename(self._path),
                    len(self._cache_images),
                    self._cache_bytes / (1024 * 1024),
                    (time.perf_counter() - t0) * 1000.0,
                )
            else:
                self._reader = QImageReader(self._path)
                self._reader.setAutoTransform(True)
        self._emit_stats_if_needed()
        self._schedule_next(delay)


class BackgroundWidget(QWidget):
    _stop_gif_worker = pyqtSignal()
    _resize_gif_worker = pyqtSignal(QSize)

    def __init__(self, manager: BackgroundManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        self.setAutoFillBackground(False)
        self.manager.changed.connect(self._on_background_changed)
        self._label = None
        self._video = None
        self._player = None
        self._gif_thread: Optional[QThread] = None
        self._gif_worker: Optional[_GifDecodeWorker] = None
        self._gif_path: str = ""
        self._active_kind: str = "unknown"
        self._active_ext: str = ""
        self._static_scaled: Optional[QPixmap] = None
        self._static_scaled_key = ("", QSize())
        self._resize_debounce = QTimer(self)
        self._resize_debounce.setSingleShot(True)
        self._resize_debounce.timeout.connect(self._on_resize_debounced)
        self._logger = _get_bg_logger()
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._cleanup)
        self._apply_media()

    def _prepare_background_overlay(self, widget: QWidget):
        widget.setGeometry(self.rect())
        widget.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        widget.setFocusPolicy(Qt.NoFocus)
        widget.lower()

    def _can_run_animated_background(self) -> bool:
        app = QApplication.instance()
        if app is None:
            return False
        if os.environ.get("PROJECT001_DISABLE_ANIMATED_BACKGROUNDS") == "1":
            return False
        if "unittest" in sys.modules or "pytest" in sys.modules:
            return False
        return app.platformName().lower() not in {"offscreen", "minimal"}

    def _show_gif_placeholder_frame(self, path: str):
        if not self._label:
            return
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        img = reader.read()
        if img.isNull():
            return
        if self.size().isValid() and not self.size().isEmpty():
            img = img.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            if img.width() > self.width() or img.height() > self.height():
                x = max(0, (img.width() - self.width()) // 2)
                y = max(0, (img.height() - self.height()) // 2)
                img = img.copy(x, y, self.width(), self.height())
        pix = QPixmap.fromImage(img)
        if pix.isNull():
            return
        self._label.setPixmap(pix)
        self._label.lower()

    def paintEvent(self, event):
        if self._video or (self._label and self._label.isVisible() and self._active_ext == ".gif"):
            super().paintEvent(event)
            return
        p = self.manager.selected_path()
        kind, ext = classify_media(p) if p else ("unknown", "")
        if ext == ".gif" or kind == "video":
            super().paintEvent(event)
            return
        pixmap, _err = self.manager.load_pixmap()
        if pixmap is not None and not pixmap.isNull() and not self._video:
            scaled = self._get_static_scaled_pixmap(pixmap)
            if scaled is None or scaled.isNull():
                super().paintEvent(event)
                return
            painter = QPainter(self)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            target = self.rect()
            painter.drawPixmap(target, scaled)
        super().paintEvent(event)

    def _cleanup(self):
        self._stop_gif()
        self._gif_path = ""
        try:
            if self._player:
                self._player.stop()
        except Exception:
            pass
        self._player = None
        if self._video:
            self._video.hide()
        self._video = None
        if self._label:
            self._label.hide()
        self._label = None
        self._active_kind = "unknown"
        self._active_ext = ""

    def _apply_media(self):
        p = self.manager.selected_path()
        kind, ext = classify_media(p) if p else ("unknown", "")
        if not p or kind == "unknown":
            self._cleanup()
            return
        if ext == ".gif":
            if self._gif_path and os.path.abspath(self._gif_path) == os.path.abspath(p) and self._label:
                self._active_kind = kind
                self._active_ext = ext
                self._prepare_background_overlay(self._label)
                if self.isVisible() and not self._gif_thread and self._can_run_animated_background():
                    self._start_gif(p)
                elif not self._can_run_animated_background():
                    self._show_gif_placeholder_frame(p)
                self._request_gif_resize()
                return
            self._cleanup()
            self._active_kind = kind
            self._active_ext = ext
            self._gif_path = p
            self._label = QLabel(self)
            self._label.setAlignment(Qt.AlignCenter)
            self._prepare_background_overlay(self._label)
            self._label.show()
            if self.isVisible() and self._can_run_animated_background():
                self._start_gif(p)
            else:
                self._show_gif_placeholder_frame(p)
            return
        if kind == "video":
            if self._video and self._player:
                self._active_kind = kind
                self._active_ext = ext
                self._prepare_background_overlay(self._video)
                return
            try:
                from PyQt5.QtCore import QUrl
            except Exception:
                QUrl = None
            self._cleanup()
            if QUrl is None:
                return
            self._active_kind = kind
            self._active_ext = ext
            self._video = QVideoWidget(self)
            self._prepare_background_overlay(self._video)
            self._player = QMediaPlayer(self)
            try:
                self._player.setMedia(QMediaContent(QUrl.fromLocalFile(p)))  # type: ignore
                self._player.setMuted(True)
                self._player.setVideoOutput(self._video)
                self._video.show()
                self._player.play()
            except Exception:
                self._cleanup()
            return

        if self._video or self._label or self._gif_thread:
            self._cleanup()
        self._active_kind = kind
        self._active_ext = ext

    def _get_static_scaled_pixmap(self, pixmap: QPixmap) -> Optional[QPixmap]:
        p = self.manager.selected_path()
        key = (os.path.abspath(p) if p else "", QSize(self.size()))
        if self._static_scaled is not None and self._static_scaled_key == key:
            return self._static_scaled
        if not pixmap or pixmap.isNull() or not self.size().isValid() or self.size().isEmpty():
            self._static_scaled = None
            self._static_scaled_key = key
            return None
        scaled = pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        if scaled.isNull():
            self._static_scaled = None
            self._static_scaled_key = key
            return None
        x = max(0, (scaled.width() - self.width()) // 2)
        y = max(0, (scaled.height() - self.height()) // 2)
        cropped = scaled.copy(x, y, self.width(), self.height())
        self._static_scaled = cropped if not cropped.isNull() else scaled
        self._static_scaled_key = key
        return self._static_scaled

    def _start_gif(self, path: str):
        self._stop_gif()
        if not path:
            return
        self._logger.info("gif_start path=%s size=%dx%d", os.path.basename(path), self.width(), self.height())
        thread = QThread()
        worker = _GifDecodeWorker(path, self.size())
        worker.moveToThread(thread)
        thread.started.connect(worker.start)
        worker.frame_ready.connect(self._on_gif_frame)
        worker.error.connect(self._on_gif_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._stop_gif_worker.connect(worker.stop)
        self._resize_gif_worker.connect(worker.set_target_size)
        self.destroyed.connect(lambda *_args, t=thread, w=worker: BackgroundWidget._shutdown_gif_thread(t, w))
        self._gif_thread = thread
        self._gif_worker = worker
        thread.start()

    @staticmethod
    def _shutdown_gif_thread(thread: Optional[QThread], worker: Optional[QObject]):
        if worker is not None:
            try:
                QMetaObject.invokeMethod(worker, "stop", Qt.QueuedConnection)
            except Exception:
                pass
        if thread is not None:
            try:
                if not thread.wait(800):
                    thread.quit()
                    thread.wait(400)
            except Exception:
                pass

    def _stop_gif(self):
        self._shutdown_gif_thread(self._gif_thread, self._gif_worker)
        self._gif_thread = None
        self._gif_worker = None

    @pyqtSlot(QImage, int, int)
    def _on_gif_frame(self, img: QImage, delay_ms: int, frame_idx: int):
        if not self._label or not self._label.isVisible():
            return
        if img.isNull():
            return
        pix = QPixmap.fromImage(img)
        if pix.isNull():
            return
        self._label.setPixmap(pix)
        self._label.lower()
        if frame_idx % 60 == 0:
            self._logger.info(
                "gif_frame idx=%d delay_ms=%d size=%dx%d",
                frame_idx,
                int(delay_ms),
                img.width(),
                img.height(),
            )

    @pyqtSlot(str)
    def _on_gif_error(self, msg: str):
        self._logger.error("gif_error path=%s error=%s", os.path.basename(self._gif_path or ""), msg)
        self._stop_gif()
        self.update()

    def _request_gif_resize(self):
        if self._active_ext != ".gif":
            return
        self._resize_debounce.start(120)

    @pyqtSlot()
    def _on_resize_debounced(self):
        if self._gif_worker and self._active_ext == ".gif":
            try:
                self._resize_gif_worker.emit(self.size())
            except Exception:
                pass

    @pyqtSlot()
    def _on_background_changed(self):
        self._static_scaled = None
        self._static_scaled_key = ("", QSize())
        self._apply_media()
        self.update()

    def resizeEvent(self, event):
        if self._label and self._label.isVisible():
            self._prepare_background_overlay(self._label)
            if self._active_ext == ".gif" and self._gif_path and not self._gif_thread:
                self._show_gif_placeholder_frame(self._gif_path)
            self._request_gif_resize()
        if self._video and self._video.isVisible():
            self._prepare_background_overlay(self._video)
        self._static_scaled = None
        self._static_scaled_key = ("", QSize())
        super().resizeEvent(event)

    def closeEvent(self, event):
        self._cleanup()
        super().closeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if self._active_ext == ".gif" and self._gif_path and self._label and not self._gif_thread and self._can_run_animated_background():
            self._start_gif(self._gif_path)

    def hideEvent(self, event):
        if self._active_ext == ".gif":
            self._stop_gif()
        super().hideEvent(event)


background_manager = BackgroundManager()
