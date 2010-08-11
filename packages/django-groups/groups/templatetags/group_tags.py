from django import template
from django.utils.encoding import smart_str
from django.core.urlresolvers import reverse, NoReverseMatch
from django.db.models import get_model
from django.db.models.query import QuerySet


register = template.Library()


class GroupURLNode(template.Node):
    def __init__(self, view_name, group, kwargs, asvar):
        self.view_name = view_name
        self.group = group
        self.kwargs = kwargs
        self.asvar = asvar
    
    def render(self, context):
        url = ""
        group = self.group.resolve(context)
        
        kwargs = {}
        for k, v in self.kwargs.items():
            kwargs[smart_str(k, "ascii")] = v.resolve(context)
        
        if group:
            bridge = group.content_bridge
            try:
                url = bridge.reverse(self.view_name, group, kwargs=kwargs)
            except NoReverseMatch:
                if self.asvar is None:
                    raise
        else:
            try:
                url = reverse(self.view_name, kwargs=kwargs)
            except NoReverseMatch:
                if self.asvar is None:
                    raise
                
        if self.asvar:
            context[self.asvar] = url
            return ""
        else:
            return url


class ContentObjectsNode(template.Node):
    def __init__(self, group_var, model_name_var, gfk_field_var, context_var):
        self.group_var = template.Variable(group_var)
        self.model_name_var = template.Variable(model_name_var)
        if gfk_field_var is not None:
            self.gfk_field_var = template.Variable(gfk_field_var)
        else:
            self.gfk_field_var = None
        self.context_var = context_var
    
    def render(self, context):
        group = self.group_var.resolve(context)
        model_name = self.model_name_var.resolve(context)
        if self.gfk_field_var is not None:
            gfk_field = self.gfk_field_var.resolve(context)
        else:
            gfk_field = None
        
        if isinstance(model_name, QuerySet):
            model = model_name
        else:
            app_name, model_name = model_name.split(".")
            model = get_model(app_name, model_name)
        
        context[self.context_var] = group.content_objects(model, gfk_field=gfk_field)
        return ""


class ObjectGroupUrlNode(template.Node):
    def __init__(self, obj, group, asvar):
        self.obj_var = template.Variable(obj)
        self.group = group
        self.asvar = asvar
    
    def render(self, context):
        url = ""
        obj = self.obj_var.resolve(context)
        group = self.group.resolve(context)
        
        try:
            url = obj.get_absolute_url(group)
        except NoReverseMatch:
            if self.asvar is None:
                raise
        
        if self.asvar:
            context[self.asvar] = url
            return ""
        else:
            return url


@register.tag
def groupurl(parser, token):
    bits = token.contents.split()
    tag_name = bits[0]
    if len(bits) < 3:
        raise template.TemplateSyntaxError("'%s' takes at least two arguments"
            " (path to a view and a group)" % tag_name)
    
    view_name = bits[1]
    group = parser.compile_filter(bits[2])
    args = []
    kwargs = {}
    asvar = None
    
    if len(bits) > 3:
        bits = iter(bits[3:])
        for bit in bits:
            if bit == "as":
                asvar = bits.next()
                break
            else:
                for arg in bit.split(","):
                    if "=" in arg:
                        k, v = arg.split("=", 1)
                        k = k.strip()
                        kwargs[k] = parser.compile_filter(v)
                    elif arg:
                        raise template.TemplateSyntaxError("'%s' does not support non-kwargs arguments." % tag_name)
    
    return GroupURLNode(view_name, group, kwargs, asvar)


@register.tag
def content_objects(parser, token):
    """
    Basic usage::
    
        {% content_objects group "tasks.Task" as tasks %}
    
    or if you need to specify a custom generic foreign key field (default is
    group)::
    
        {% content_objects group "tasks.Task" "content_object" as tasks %}
    """
    bits = token.split_contents()
    if len(bits) not in [5, 6]:
        raise template.TemplateSyntaxError("'%s' requires five or six arguments." % bits[0])
    else:
        if len(bits) == 5:
            return ContentObjectsNode(bits[1], bits[2], None, bits[4])
        else:
            return ContentObjectsNode(bits[1], bits[2], bits[3], bits[5])


@register.tag
def object_group_url(parser, token):
    """
    given an object and an optional group, call get_absolute_url passing the
    group variable::
    
        {% object_group_url task group %}
    """
    bits = token.contents.split()
    tag_name = bits[0]
    if len(bits) < 3:
        raise template.TemplateSyntaxError("'%s' takes at least two arguments"
            " (object and a group)" % tag_name)
    
    obj = bits[1]
    group = parser.compile_filter(bits[2])
    
    if len(bits) > 3:
        if bits[3] != "as":
            raise template.TemplateSyntaxError("'%s' requires the forth"
                " argument to be 'as'" % tag_name)
        try:
            asvar = bits[4]
        except IndexError:
            raise template.TemplateSyntaxError("'%s' requires an argument"
                " after 'as'" % tag_name)
    
    return ObjectGroupUrlNode(obj, group, asvar)
