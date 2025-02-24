from . import saved_camera_views

def register():
    saved_camera_views.register()

def unregister():
    saved_camera_views.unregister()

if __name__ == "__main__":
    register()