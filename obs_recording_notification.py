import tkinter as tk
from tkinter import *
import threading
import obspython as obs

try:
    import winsound
    SOUNDS_AVAILABLE = True
except ImportError:
    SOUNDS_AVAILABLE = False

# --------------------------------------------------

class Config:
    sounds_enabled = True
    position_center = True  # True=center, False=top-right


def _play_sound_thread(alias, fallback_freq, fallback_duration, fallback_count):
    """Internal: play sound in separate thread to avoid OBS audio conflicts."""
    try:
        winsound.PlaySound(alias, winsound.SND_ALIAS)  # Sync in thread ensures completion
    except:
        try:
            for _ in range(fallback_count):
                winsound.Beep(fallback_freq, fallback_duration)
        except:
            pass


def _warmup_sound():
    """Initialize Windows audio system by playing a silent sound."""
    if SOUNDS_AVAILABLE:
        try:
            winsound.PlaySound(None, winsound.SND_ASYNC)
        except:
            pass


def play_sound(alias, fallback_freq, fallback_duration, fallback_count=1):
    """Play a Windows system sound with fallback beep(s)."""
    if not SOUNDS_AVAILABLE or not Config.sounds_enabled:
        return
    threading.Thread(
        target=_play_sound_thread,
        args=(alias, fallback_freq, fallback_duration, fallback_count),
        daemon=True
    ).start()


class Application(tk.Frame):
    def __init__(self, master=None):
        tk.Frame.__init__(self, master)
        self.config(bg="#1a1a1a")
        self.pack()

        # Dynamic position based on config
        self.update_position()

        self.master.attributes('-alpha', 0.0)  # Start hidden
        self.master.configure(bg='#0f0f0f')  # Darker background
        self.master.overrideredirect(1)  # Borderless window
        self.master.attributes('-topmost', True)  # Always on top

        # Add rounded corners effect
        self.master.attributes('-transparentcolor', '#0f0f0f')
        self.config(bg='#0f0f0f')

        self.is_animating = False
        self.pending_notification = False
        self._fade_timer = None
        self._fadeout_timer = None

        # Modern container frame with subtle border
        container = Frame(self, bg='#252525', bd=0, highlightthickness=1,
                         highlightbackground='#404040', highlightcolor='#404040')
        container.pack(padx=5, pady=5, fill=BOTH, expand=True)

        # Calculate scale factor based on screen width
        screen_w = self.master.winfo_screenwidth()
        self.scale = max(1.0, screen_w / 1920)  # 1.0 at 1080p, scales up for higher res
        canvas_size = int(30 * self.scale)
        font_size = int(11 * self.scale)

        self.canvas = Canvas(container, height=canvas_size, width=canvas_size, bg='#252525', highlightthickness=0)
        self.canvas.grid(row=0, column=0, padx=(10,5), pady=5)
        self._draw_indicator('recording', 'started')

        self.label = Label(container, text="Recording Started", font=('Segoe UI', font_size, 'bold'))
        self.label.grid(row=0, column=1, padx=(0,15), pady=5)
        self.label.config(bg="#252525", fg="#ffffff")

    def _draw_indicator(self, ntype, state):
        """Draw the notification indicator icon, scaled for resolution."""
        s = self.scale
        self.canvas.delete("all")
        # Shadow and border (scaled)
        self.canvas.create_oval(25*s, 25*s, 5*s, 5*s, outline='#000000', fill='#000000')
        self.canvas.create_oval(24*s, 24*s, 6*s, 6*s, outline='#404040', fill='#252525')

        if ntype == 'recording':
            if state == 'started':
                self.canvas.create_oval(22*s, 22*s, 8*s, 8*s, fill='#ff3333')
            elif state == 'paused':
                self.canvas.create_rectangle(12*s, 10*s, 15*s, 20*s, fill='#ff9900', outline='#ff9900')
                self.canvas.create_rectangle(17*s, 10*s, 20*s, 20*s, fill='#ff9900', outline='#ff9900')
            elif state == 'unpaused':
                self.canvas.create_polygon(12*s, 10*s, 12*s, 20*s, 22*s, 15*s, fill='#00cc00', outline='#00cc00')
            else:  # saved
                self.canvas.create_line(10*s, 15*s, 15*s, 20*s, fill='#00cc00', width=int(3*s))
                self.canvas.create_line(15*s, 20*s, 22*s, 10*s, fill='#00cc00', width=int(3*s))
        elif ntype == 'replay':
            self.canvas.create_oval(22*s, 22*s, 8*s, 8*s, fill='#0099ff')

    def update_position(self):
        """Update window position and size based on screen resolution."""
        screen_w = self.master.winfo_screenwidth()
        screen_h = self.master.winfo_screenheight()
        # Scale window: width = 15% of screen, height proportional
        w = max(300, min(500, int(screen_w * 0.15)))
        h = max(55, int(w * 0.20))
        if Config.position_center:
            x = (screen_w - w) // 2
            y = (screen_h - h) // 2
        else:  # top-right
            x = screen_w - w - 10
            y = 20
        self.master.geometry(f'{w}x{h}+{x}+{y}')
        self.master.update_idletasks()


    def fade_in(self):
        current = float(self.master.attributes('-alpha'))
        if current < 0.9:
            current += 0.1
            self.master.attributes('-alpha', current)
            self._fade_timer = self.after(30, self.fade_in)
        else:
            self._fadeout_timer = self.after(3000, self.fade_out)  # Stay visible for 3 seconds

    def fade_out(self):
        current = float(self.master.attributes('-alpha'))
        if current > 0.1:
            current -= 0.1
            self.master.attributes('-alpha', current)
            self._fade_timer = self.after(30, self.fade_out)
        else:
            self.is_animating = False
            # Clear notification state after fade out completes
            if hasattr(self, 'notification_type'):
                delattr(self, 'notification_type')
                delattr(self, 'notification_state')


    def check_loop_status(self):
        if not hasattr(self, 'notification_type'):
            self.after(100, self.check_loop_status)
            return

        # Only start new animation if not animating OR if there's a pending notification
        if self.is_animating and not self.pending_notification:
            self.after(100, self.check_loop_status)
            return

        # If pending notification, interrupt current animation
        if self.pending_notification:
            if self._fade_timer:
                self.after_cancel(self._fade_timer)
            if self._fadeout_timer:
                self.after_cancel(self._fadeout_timer)
            self.master.attributes('-alpha', 0.0)
            self.pending_notification = False

        self.is_animating = True

        # Update label text and indicator
        labels = {
            ('recording', 'started'): "Recording Started",
            ('recording', 'paused'): "Recording Paused",
            ('recording', 'unpaused'): "Recording Resumed",
            ('recording', 'saved'): "Recording Saved",
            ('replay', 'saved'): "Replay Saved",
        }
        self.label.config(text=labels.get((self.notification_type, self.notification_state), "Notification"))
        self._draw_indicator(self.notification_type, self.notification_state)

        self.fade_in()
        self.after(100, self.check_loop_status)
    
 
# Global reference to application instance
app_instance = None

def runtk():  # runs in background thread
    global app_instance
    app_instance = Application()                        
    app_instance.master.title('OBS Recording Notification')  
    app_instance.check_loop_status()
    app_instance.mainloop()
    app_instance = None  # Clear reference when window closes
        
    
thd = threading.Thread(target=runtk)   # gui thread
thd.daemon = True  # background thread will exit if main thread exits



# ----------------------------   OBS script    ------------------------------------------------------------

def frontend_event_handler(data):
    global app_instance

    if data == obs.OBS_FRONTEND_EVENT_FINISHED_LOADING:
        if not thd.is_alive():
            thd.start()
        _warmup_sound()  # Initialize audio system
        return

    if not app_instance or not hasattr(app_instance, 'master') or not app_instance.master.winfo_exists():
        return

    if data == obs.OBS_FRONTEND_EVENT_RECORDING_STARTING:
        play_sound("DeviceConnect", 800, 200)
        app_instance.after(0, lambda: (
            setattr(app_instance, 'notification_type', 'recording'),
            setattr(app_instance, 'notification_state', 'started'),
            setattr(app_instance, 'pending_notification', True),
            app_instance.check_loop_status()
        ))

    elif data == obs.OBS_FRONTEND_EVENT_RECORDING_STOPPED:
        play_sound("DeviceDisconnect", 400, 300)
        app_instance.after(0, lambda: (
            setattr(app_instance, 'notification_type', 'recording'),
            setattr(app_instance, 'notification_state', 'saved'),
            setattr(app_instance, 'pending_notification', True),
            app_instance.check_loop_status()
        ))

    elif data == obs.OBS_FRONTEND_EVENT_RECORDING_PAUSED:
        play_sound("SystemHand", 600, 150, 2)
        app_instance.after(0, lambda: (
            setattr(app_instance, 'notification_type', 'recording'),
            setattr(app_instance, 'notification_state', 'paused'),
            setattr(app_instance, 'pending_notification', True),
            app_instance.check_loop_status()
        ))

    elif data == obs.OBS_FRONTEND_EVENT_RECORDING_UNPAUSED:
        play_sound("SystemAsterisk", 600, 100, 2)
        app_instance.after(0, lambda: (
            setattr(app_instance, 'notification_type', 'recording'),
            setattr(app_instance, 'notification_state', 'unpaused'),
            setattr(app_instance, 'pending_notification', True),
            app_instance.check_loop_status()
        ))

    elif data == obs.OBS_FRONTEND_EVENT_REPLAY_BUFFER_SAVED:
        play_sound("SystemNotification", 1000, 100, 3)
        app_instance.after(0, lambda: (
            setattr(app_instance, 'notification_type', 'replay'),
            setattr(app_instance, 'notification_state', 'saved'),
            setattr(app_instance, 'pending_notification', True),
            app_instance.check_loop_status()
        ))



def script_description():
    return ("OBS Shadowplay-style Notification\n\n"
            "Shows visual + audio notifications for:\n"
            "• Recording Start/Stop/Pause/Resume\n"
            "• Replay Buffer Saved\n\n"
            "Settings:\n"
            "• Enable/disable sounds\n"
            "• Center or top-right position\n\n"
            "Restart OBS after adding the script\n\n"
            "Requires Python 3.6.8 with Tkinter")


def script_defaults(settings):
    obs.obs_data_set_default_bool(settings, "sounds_enabled", True)
    obs.obs_data_set_default_bool(settings, "position_center", True)


def script_properties():
    props = obs.obs_properties_create()
    obs.obs_properties_add_bool(props, "sounds_enabled", "Enable sound notifications")
    obs.obs_properties_add_bool(props, "position_center", "Center notification (uncheck for top-right)")
    return props


def script_update(settings):
    Config.sounds_enabled = obs.obs_data_get_bool(settings, "sounds_enabled")
    Config.position_center = obs.obs_data_get_bool(settings, "position_center")
    if app_instance and hasattr(app_instance, 'master') and app_instance.master.winfo_exists():
        app_instance.after(0, app_instance.update_position)


obs.obs_frontend_add_event_callback(frontend_event_handler)
