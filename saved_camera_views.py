import bpy
import gpu
import traceback
import random
from gpu_extras.presets import draw_texture_2d
from bpy.props import *
from bpy.types import PropertyGroup, UIList, Operator

random_id_source = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"

def get_id():
	return "."+("".join(random.sample(random_id_source, 10)))

def save_preview(context, id):
	scene = context.scene
	props = context.scene.camera_saved
	width = int(context.scene.render.resolution_x*0.5)
	height = int(context.scene.render.resolution_y*0.5)

	offscreen = gpu.types.GPUOffScreen(width, height)

	view_matrix = scene.camera.matrix_world.inverted()

	projection_matrix = scene.camera.calc_matrix_camera(
		context.evaluated_depsgraph_get(), x=width, y=height)
	
	current_type = context.space_data.shading.type
	current_overlays = context.space_data.overlay.show_overlays

	context.space_data.shading.type = props.shading_type
	context.space_data.overlay.show_overlays = props.toggle_overlays

	offscreen.draw_view3d(
		scene,
		context.view_layer,
		context.space_data,
		context.region,
		view_matrix,
		projection_matrix,
		do_color_management=True)

	gpu.state.depth_mask_set(False)
	draw_texture_2d(offscreen.texture_color, (10, 10), width, height)
	
	pixels = offscreen.texture_color.read()

	if bpy.data.images.get(id):
		new_image = bpy.data.images[id]
		new_image.unpack()
	else:
		new_image = bpy.data.images.new(id, width, height)

	new_image.scale(width, height)
	pixels.dimensions = width * height * 4
	new_image.pixels = [v / 255 for v in pixels]
	
	new_image.id_data.preview_ensure()
	new_image.preview.reload()

	context.space_data.shading.type = current_type
	context.space_data.overlay.show_overlays = current_overlays

	new_image.pack()

	new_image.use_fake_user = True

class SAVECAMS_DATA_Property(PropertyGroup):
	cindex  : IntProperty(name='Index')
	name    : StringProperty(name="Saved name", default="Camera")
	id    : StringProperty(name="Saved ID", default="")
	type : EnumProperty(default="ORTHO",name = "Saved Type",
	items= [
	("ORTHO","Orthographic",""),
	("PERSP","Perspective",""),
	("PANO","Panoramic",""),
	])

	camLocs : FloatVectorProperty(name = "Saved Location")
	camRots : FloatVectorProperty(name="Saved Rotation")
	flen    : FloatProperty(name='Saved Focal Length')
	ortho   : FloatProperty(name='Saved Orthographic Scale')
	res_x   : IntProperty(name='Saved X Resolution')
	res_y   : IntProperty(name='Saved Y Resolution')

class SAVECAMS_Property(PropertyGroup):
	def index_change(self, context):
		props = context.scene.camera_saved
		
		for i, a in enumerate(context.scene.camera_saved.saved_data):
			if a.name == context.scene.camera_saved.saved_data[context.scene.camera_saved.saved_data_index].name:
				if props.previews!=str(context.scene.camera_saved.saved_data_index):
					try:
						props.previews = str(context.scene.camera_saved.saved_data_index)
					except Exception as e:
						print(e)
		bpy.ops.camera.assign_saved(item=context.scene.camera_saved.saved_data_index)

	def previews_items(self, context):
		try:
			enum_items = [
				(str(i), item.name, item.id, bpy.data.images[item.id].preview.icon_id, i)
				for i, item in enumerate(context.scene.camera_saved.saved_data) if bpy.data.images.get(item.id)
			]
			return enum_items
		except Exception as e:
			traceback.print_exc()
			return []

	def update_previews(self, context):
		context.scene.camera_saved.saved_data_index = int(self.previews)
		bpy.ops.camera.assign_saved(item=context.scene.camera_saved.saved_data_index)

	previews : EnumProperty(
				items=previews_items,
				update = update_previews
			)
	
	shading_type : EnumProperty(default = 'RENDERED',
							items = [('SOLID', 'Solid', '', 'SHADING_SOLID', 0),
									('RENDERED', 'Rendered', '','SHADING_RENDERED', 1),
									],
							name="Preview Shading Type"
									)

	toggle_overlays : BoolProperty(default=False,name="Toggle Overlay")
	toggle_preview : BoolProperty(default=True,name="Toggle Preview")
	
	toggle_lens : BoolProperty(default=False,name="Toggle Lens")
	toggle_type : BoolProperty(default=False,name="Toggle Type")
	toggle_resolution : BoolProperty(default=False,name="Toggle resolution")

	saved_data : CollectionProperty(type=SAVECAMS_DATA_Property)
	saved_data_index : IntProperty(
			name = "Camera Scene Index",
			default = 0,
			min = 0,
			update=index_change
			)

class SAVECAMS_UL_saved_list(UIList):
	def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
		props = context.scene.camera_saved
		cam = item
		row = layout.row(align=True)

		reassign = row.operator("camera.reassign_saved",text="", icon="FILE_REFRESH", emboss=False)
		reassign.item= index

		row.prop(cam, "name", text="", icon_value=icon)
		if props.toggle_type:
			row.prop(cam, "type", text="", icon="NONE")
		if props.toggle_lens:
			if cam.type == "PERSP":
				row.prop(cam, "flen", text="", icon="NONE")
			elif cam.type == "ORTHO":
				row.prop(cam, "ortho", text="", icon="NONE")
		if props.toggle_resolution:
			row.prop(cam, "res_x", text="X", icon="NONE")
			row.prop(cam, "res_y", text="Y", icon="NONE")
			row.separator()

		remove = row.operator("camera.remove_saved", text="", icon='X', emboss=False)
		remove.item= index

class SAVECAMS_OT_add_saved(Operator):
	bl_idname = "camera.add_saved"
	bl_label = "Add"
	bl_description = "Add cam"

	def execute(self, context):
		scene = context.scene
		if context.object.type=="CAMERA":
			obj = context.object
		else:
			obj = context.scene.camera

		item = context.scene.camera_saved.saved_data.add()
		item.name = obj.name + " " + str(len(context.scene.camera_saved.saved_data))
		item.type = obj.data.type
		item.camLocs = obj.location
		item.camRots = obj.rotation_euler
		item.flen = obj.data.lens
		item.ortho = obj.data.ortho_scale
		item.res_x = context.scene.render.resolution_x
		item.res_y = context.scene.render.resolution_y
		context.scene.camera_saved.saved_data_index = len(context.scene.camera_saved.saved_data)-1

		id = get_id()
		item.id = id
		save_preview(context, id)

		return{'FINISHED'}

class SAVECAMS_OT_remove_saved(Operator):
	bl_idname = "camera.remove_saved"
	bl_label = "Remove"
	bl_description = "Remove cam"

	item : IntProperty(default=0,name="Item")

	@classmethod
	def poll(cls, context):
		return len(context.scene.camera_saved.saved_data) > 0

	def execute(self, context):
		# index = context.scene.camera_saved.saved_data_index
		index = self.item

		item = context.scene.camera_saved.saved_data[self.item]

		image = bpy.data.images.get(item.id)

		bpy.data.images.remove(image)

		context.scene.camera_saved.saved_data.remove(index)
		for cam in context.scene.camera_saved.saved_data:
			if cam.cindex > index:
				cam.cindex = cam.cindex - 1
		if len(context.scene.camera_saved.saved_data) == index:
			context.scene.camera_saved.saved_data_index = index-1
		else:
			context.scene.camera_saved.saved_data_index = index
			
		return{'FINISHED'}

class SAVECAMS_OT_assign_saved(Operator):
	bl_idname = "camera.assign_saved"
	bl_label = "Assign"
	bl_description = "Assign cam"

	item : IntProperty(default=0,name="Item")

	@classmethod
	def poll(cls, context):
		return len(context.scene.camera_saved.saved_data) > 0

	def execute(self, context):
		if context.object.type=="CAMERA":
			cam = context.object
		else:
			cam = bpy.context.scene.camera

		item = context.scene.camera_saved.saved_data[self.item]
		cam.data.type = item.type
		cam.location = item.camLocs
		cam.rotation_euler = item.camRots
		cam.data.lens = item.flen
		cam.data.ortho_scale = item.ortho
		context.scene.render.resolution_x = item.res_x
		context.scene.render.resolution_y = item.res_y

		return{'FINISHED'}

class SAVECAMS_OT_reassign_saved(Operator):
	bl_idname = "camera.reassign_saved"
	bl_label = "Reassign"
	bl_description = "Reassign selected cam"

	item : IntProperty(default=0,name="Item")

	@classmethod
	def poll(cls, context):
		return len(context.scene.camera_saved.saved_data) > 0

	def execute(self, context):
		if context.object.type=="CAMERA":
			cam = context.object
		else:
			cam = bpy.context.scene.camera

		item = context.scene.camera_saved.saved_data[self.item]
		item.camLocs = cam.location
		item.camRots = cam.rotation_euler
		item.flen = cam.data.lens
		item.ortho = cam.data.ortho_scale
		item.res_x = context.scene.render.resolution_x
		item.res_y = context.scene.render.resolution_y

		save_preview(context, item.id)
		
		context.scene.camera_saved.saved_data_index = self.item

		self.report({'INFO'}, "Updated by current camera")
		return{'FINISHED'}

class SAVECAMS_OT_add_saved_from_view(Operator):
	bl_idname = "camera.add_saved_from_view"
	bl_label = "Add from View"
	bl_description = "Add selected cam from view"

	@classmethod
	def poll(cls, context):
		for area in bpy.context.screen.areas:
			if area.type == 'VIEW_3D':
				return  area.spaces[0].region_3d.view_perspective != 'CAMERA'

	def execute(self, context):
		bpy.ops.view3d.camera_to_view()
		bpy.ops.camera.add_saved()
		return{'FINISHED'}

class SAVECAMS_OT_saved_list_up(Operator):
	bl_idname = "camera.saved_list_up"
	bl_label = "Cycle Up"
	bl_description = "Cycle up through cam views"

	@classmethod
	def poll(cls, context):
		return len(context.scene.camera_saved.saved_data) > 0

	def execute(self, context):
		if context.scene.camera_saved.saved_data_index == 0:
			context.scene.camera_saved.saved_data_index = len(context.scene.camera_saved.saved_data) - 1
		else:
			context.scene.camera_saved.saved_data_index -= 1
		bpy.ops.camera.assign_saved(item=context.scene.camera_saved.saved_data_index)
		return{'FINISHED'}

class SAVECAMS_OT_saved_list_down(Operator):
	bl_idname = "camera.saved_list_down"
	bl_label = "Cycle Down"
	bl_description = "Cycle down through cam views"

	@classmethod
	def poll(cls, context):
		return len(context.scene.camera_saved.saved_data) > 0

	def execute(self, context):
		if context.scene.camera_saved.saved_data_index == len(context.scene.camera_saved.saved_data) - 1:
			context.scene.camera_saved.saved_data_index = 0
		else:
			context.scene.camera_saved.saved_data_index += 1
		bpy.ops.camera.assign_saved(item=context.scene.camera_saved.saved_data_index)
		return{'FINISHED'}

def draw_save_cam(context, box):
	props = context.scene.camera_saved

	row = box.row()
	row.prop(props,"toggle_preview", text="Preview", icon = "RESTRICT_VIEW_OFF" if props.toggle_preview else "RESTRICT_VIEW_ON", toggle = True)
	row = row.row(align=True)
	row.active = props.toggle_preview
	row.prop(props,"shading_type", expand = True)
	row.separator()
	row.prop(props,"toggle_overlays", text="", icon = "OVERLAY", toggle = True)

	row = box.row(align=True)
	row.prop(props,"toggle_type",text="Type", toggle = True)
	row.prop(props,"toggle_lens",text="Lens", toggle = True)
	row.prop(props,"toggle_resolution",text="Reso", toggle = True)

	if len(context.scene.camera_saved.saved_data) > 0:	
		if props.toggle_preview:
			item =context.scene.camera_saved.saved_data[context.scene.camera_saved.saved_data_index]
			box.label(text= f"{item.name} - {item.res_x} x {item.res_y}   Lens: {item.flen}")
			box.template_icon_view(props, "previews", scale=15, scale_popup=7.0, show_labels=True)

	row = box.row()
	col = row.column()
	col.template_list("SAVECAMS_UL_saved_list", "", context.scene.camera_saved, "saved_data", context.scene.camera_saved, "saved_data_index")

	col = row.column()
	col.operator("camera.add_saved_from_view", icon = "ZOOM_IN", text = "")
	sub = col.column(align=True)
	sub.operator("camera.add_saved", icon='ADD', text="")
	remove = sub.operator("camera.remove_saved", text="", icon='REMOVE')
	remove.item = context.scene.camera_saved.saved_data_index
	
	sub = col.column(align=True)
	sub.operator("camera.saved_list_up", icon="TRIA_UP", text='')
	sub.operator("camera.saved_list_down", icon="TRIA_DOWN", text='')

class SAVECAMS_PT_View3D(bpy.types.Panel):
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_label = "Saved Camera Views"
	bl_idname = "SAVECAMS_PT_View3D"
	bl_category = "Camera Views"

	@classmethod
	def poll(cls, context):
		if context.object and context.object.type == 'CAMERA':
			return True

	def draw(self, context):
		layout = self.layout.box()
		draw_save_cam(context, layout)

class SAVECAMS_PT_Properties(bpy.types.Panel):
	"""Add shake to your Cameras."""
	bl_label = "Saved Camera Views"
	bl_idname = "SAVECAMS_PT_Properties"
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = "data"

	@classmethod
	def poll(cls, context):
		return context.active_object.type == 'CAMERA'
	
	def draw(self, context):
		layout = self.layout.box()
		draw_save_cam(context, layout)


classes = (
		SAVECAMS_OT_add_saved_from_view,
		SAVECAMS_OT_add_saved,
		SAVECAMS_OT_assign_saved,
		SAVECAMS_OT_saved_list_down,
		SAVECAMS_OT_saved_list_up,
		SAVECAMS_OT_reassign_saved,
		SAVECAMS_OT_remove_saved,
		SAVECAMS_DATA_Property,
		SAVECAMS_Property,
		SAVECAMS_UL_saved_list,
		SAVECAMS_PT_View3D,
		SAVECAMS_PT_Properties,
)

def register():
	from bpy.utils import register_class
	for cls in classes:
		register_class(cls)

	bpy.types.Scene.camera_saved = bpy.props.PointerProperty(type=SAVECAMS_Property)

def unregister():
	from bpy.utils import unregister_class
	for cls in reversed(classes):
		unregister_class(cls)

	del bpy.types.Scene.camera_saved

if __name__ == "__main__":
	register()
