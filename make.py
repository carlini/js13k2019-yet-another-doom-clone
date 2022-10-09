## make.py -- Do a bunch more ugly JS compression.

## Copyright (C) 2019, Nicholas Carlini <nicholas@carlini.com>.
##
## This program is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program.  If not, see <http://www.gnu.org/licenses/>.


import re
import os
import string

def encode(num,orig):
    #print("set", num, orig)
    return str(num) # +orig
    num += 1
    out = ""
    while num > 0:
        out += (string.ascii_letters)[num%(26)]
        num //= (26)
    return out



def compress_common_names(data):
    """
    Go through and compress gl.____ and window.____ with a short version
    of the command looking at specific character indexs.
    On startup the code will rewrite the window object to make this work.
    """

    # Through brute force search, indexs -8, -2, and 3 are the best to choose.
    new_toks = [{x: ("_"*10+x)[-8]+x[-2]+x[3] for x in x.split() if len(x) >= 4} for x in open("rebind_props.txt").readlines()]

    # See if any of the tokens we're about to remove appears anywhere
    # eles other than as a .[foo] -- if so, it's probably not something
    # we should be doing.
    # For example, 'locations' is a property of a variable, but we
    # use a 'locations' variable somewhere.
    # Warn about that.
    skip_replaces = set(['.createFramebuffer', '.texParameteri', '.uniformMatrix4fv', '.createShader', '.createBuffer', '.uniform4fv', '.generateMipmap', '.getShaderParameter', '.createRenderbuffer', '.deleteShader', '.RG', '.uniform1f', '.uniform1i', '.LINEAR', '.getProgramParameter', '.attachShader', '.id', '.style', '.innerHeight', '.start'])
    for line in open("rebind_props.txt").readlines()[-2:]:
        for x in line.split():
            skip_replaces.add("."+x)

    # These are the tokens that break the rules. Don't rewrite them.
    for new_toks_dict in new_toks:
        for tok in new_toks_dict.keys():
            if len(re.findall(r"[^\.a-zA-Z]"+tok, data)) > 0:
                skip_replaces.add(tok)

    any_letter_or_digit = set(string.ascii_letters+string.digits+"_")

    for prop in set(re.findall(r"\.[$a-z_A-Z][$a-z_A-Z0-9]*", data)):
        if "QWQWQ" in prop:
            # Sometimes I don't want to rewrite it (e.g., the one before
            # the actual adjustment of the window object).
            data = data.replace(prop, prop.replace("QWQWQ","!REMOVEME!"))
        elif any(prop[1:] in x for x in new_toks):
            new_name = [x[prop[1:]] for x in new_toks if prop[1:] in x]
            assert len(set(new_name)) == 1
            if len(prop) > 4 and prop not in skip_replaces:
                new_name = encode(new_name[0],prop[1:])
                #print("Found", prop, new_name)
                #data = re.sub(r"\."+prop+"(?=[^a-zA-Z0-9_=])", "."+new_name, data)
                new_data = ""
                for i,val in enumerate(data.split(prop)):
                    if i == 0:
                        new_data += val
                    elif new_data.rpartition(".")[2] == "prototype":
                        new_data += prop+val
                    elif new_data[-1] == '.':
                        new_data += prop+val
                    elif val[0] in any_letter_or_digit:
                        new_data += prop+val
                    elif '=' in val[:5]:
                        new_data += prop+val
                    else:
                        new_data += "."+new_name+val
                data = new_data
            else:
                #print("COULD NOT COMPRESS", prop, new_name)
                pass
    return data.replace("!REMOVEME!","")

def compress_webgl_variables(original_data, data):
    """
    Do some simple shader compression. This mostly just looks for variables
    to rewrite and doesn't do much else. There is better compression
    available and I use that for the final product, but this gets 95% of
    the way there.
    """
    shaders = []
    is_in_shader = False

    # 1. Scan the file to find all of the shaders.
    for line in original_data.split("\n"):
        if "#version 300 es" in line or "//SHADER" in line:
            is_in_shader = True
        elif is_in_shader:
            if '`' in line:
                is_in_shader = False
            else:
                #print("Add", line.split("//")[0])
                shaders.append(line.split("//")[0])

    # 2. Look for the variables in the shader.
    shader_variables = []
    keywords = "bool vec2 vec3 vec4 mat3 mat4 sampler2D float int".split()
    all_new_words = []
    for line in shaders:
        new_words = []
        for kw in keywords:
            if kw in line:
                options = re.findall("^ [a-zA-Z_0-9,]*",line.split(kw)[1])
                if len(options) > 0:
                    new_words += [x.strip() for x in options[0].split(",")]
        new_words = [x for x in new_words if x not in ["gl_Position"] and len(x) > 1]
        all_new_words.extend(new_words)

    # 3. Rewrite the variables to use ascii letters (except i/j)
    letters = string.ascii_letters.replace("i","").replace("j","")
    letters = [x for x in letters]
    letters = letters + [a+b for a in letters for b in letters]
    for i,var_name in enumerate(sorted(set(all_new_words),key=len)[::-1]):
        data = data.replace(var_name, letters[i])
    data = data.replace(r'"\n"', "$SLASH_N$")
    data = data.replace(r"\n"," ")

    # 4. Remove all duplicate whitespace
    for _ in range(10):
        data = data.replace("  ", " ")

    # 5. Remove whitespace around symbols
    for symbol in "(){}<>=-+*/,&|;?:":
        for _ in range(5):
            data = data.replace(" "+symbol, symbol)
            data = data.replace(symbol+" ", symbol)
    data = data.replace("$SLASH_N$",r'"\n"')
    data = data.replace("#version 300 es","#version 300 es\\n")
    data = data.replace("//SHADER", "")
    
    return data
        
def compress():
    files = ["jsfxr.js", "audio.js", "utils.js", "objects.js", "graphics.js", "game.js", "map.js", "webgl.js", "shaders/program1.js"]
    #raw = "".join([chr(x) for x in open("src/raw_data.js","rb").read()])
    #print(raw)

    hdr =  """var Math_sin = Mathq.sin,
    Math_cos = Mathq.cos,
    Math_PI = Mathq.PI,
    Math_random = Mathq.random,
    Math_abs = Mathq.abs,
    Math_max = Mathq.max;"""

    
    original_data = '(()=>{"use strict";' + "".join(open("src/"+x).read() for x in files) + hdr + "})()"
    
    newdat = ""
    for line in original_data.split("\n"):
        if "// DEBUGONLY" in line:
            continue
        elif "// QQ" in line:
            newdat += line.replace(".", ".QWQWQ")+"\n"
        elif "/*HACK*/" in line:
            newdat += line.replace("/*HACK*/","zzHACK")+"\n"
        elif 'console.log' in line:
            continue
        else:
            newdat += line+"\n"


    """
    newdat = newdat.split("STORE_DATA(")
    dat = newdat[0]
    newdat = newdat[1:]
    data_cache = []
    for piece in newdat:
        args = piece[:piece.index(")")]
        rest = piece[piece.index(")")+1:]
        if 'x' in args:
            # it's the definition
            dat += "STORE_DATA("+piece
            continue
        args = re.sub(r'\s+', '', args)
        #low, _, args = args.partition(',')
        #high, _, args = args.partition(',')
        #low, high = float(low), float(high)
        print(args)
        args = [float(x) if '*' not in x else eval(x) for x in args.replace(",]","]")[1:-1].split(",")]
        print(args)
        dat += "LOAD_DATA(%d,%d)"%(len(data_cache), len(args))
        data_cache += args
        
        dat += rest
        
    newdat = dat.replace("DATA_ARRAY=null", "DATA_ARRAY="+str(data_cache))
    """

    ### ATTEMPT 0
    newdat = re.sub(r'\("([^"]*)"\)', "`\\1`", newdat)
    newdat = re.sub(r"\('([^']*)'\)", "`\\1`", newdat)

    ### ATTEMPT 1
    for each in ["Math.sin", "Math.cos", "Math.PI", "Math.random", "Math.abs", "Math.max"]:
        newdat = newdat.replace(each, each.replace(".","_"))
    newdat = newdat.replace("Mathq", "Math")
    hdr = ""
        
    ### ATTEMPT 2
    src="gl.FLOAT, gl.TEXTURE0, gl.RGBA32F, gl.RGBA, gl.RG32F, gl.TEXTURE_WRAP_T, gl.TEXTURE_WRAP_S, gl.TEXTURE20, gl.FRONT, gl.DYNAMIC_DRAW, gl.DEPTH_ATTACHMENT, gl.COLOR_ATTACHMENT0".split(", ")
    dst=[5126, 33984, 34836, 6408, 33328, 10243, 10242, 34004, 1028, 35048, 36096, 36064]
    for s,d in zip(src,dst):
        newdat = newdat.replace(s,str(d))
    
    """
    newdat = newdat.replace("//*", "//")

    while '/*' in newdat:
        first = newdat[:newdat.index("/*")]
        rest = newdat[newdat.index("/*"):]
        newdat = first + rest[rest.index("*/")+2:]

    while '//' in newdat:
        first = newdat[:newdat.index("//")]
        rest = newdat[newdat.index("//"):]
        newdat = first + rest[rest.index("\n"):]
    """

    ### ATTEMPT 3
    #for i in range(3):
    #    newdat = re.sub(r"[a-zA-Z_][a-zA-Z0-9_]*_r"+str(i),"LOCAL"+str(i), newdat)
    #newdat = re.sub(r"var LOCAL","LOCAL", newdat)

    # TODO is it shorter to actually not do this?
    #newdat = re.sub("function *([a-zA-Z_0-9]+) *\\(([^{]+)",
    #                "var \\1 = (\\2 =>",
    #                newdat)


    ## Now we're going to white-list all the props we're allowed to mangle
    ## Then replace them with __NUM and tell uglify it's allowed to mangle
    ## underscore variables.
    rewrite = "position add theta scalar_multiply sprite state subtract shadow_camera dead velocity theta2 distance_to lerp render waypoint post_filter floor_height a_colors vector_length solid recoil ceil_height brightness theta3 still parallel_dir a_positions _params spins parent_obj get_floor_height floor_light cel_light vertices transparent sprite2 rebuffer reset patrol get_region_at lines draw_scene doorclose dimensions components a_normals vector_multiply  texture_direction camera_is_light state rotation update regions dimensions onhit ceil_light synthWave negate collect2 collect compute_shadowmap cross dooropen length_squared old_color reset_color_timer totalReset buffers time speedinv framebuffer spin_rate floor_cache count copy slow shadow grounded attacking dynamic_shadow is_in_region levels ghost sprites load_level cull timer aq_angle floor_texture ceil_texture boom aspect wall_texture put_objects collect_dist remake backup_levels texture_id height_offset gethelp clock all_levels ".split() # xyz xyzw
    
    # Look for the props to rewrite with this command here
    # cat build/comp3.js | grep -o "\.[a-zA-Z_][a-zA-Z_0-9]*" | grep "....." | sort | uniq -c | sort -nr
    
    newdat = "@".join(re.split('([^a-zA-Z0-9_$])', newdat))
    for i,each in enumerate(rewrite):
        what = "__"+encode(i,"")
        newdat = newdat.replace("@"+each+"@","@"+what+"@")
    newdat = newdat.replace("@","")

    open("/tmp/out.js","w").write(newdat)

    data = os.popen("uglifyjs --compress --mangle --mangle-props regex=/^_.*/ -- /tmp/out.js > build/comp.js").read()
    data = open("build/comp.js").read()
    data = data[19:-6]

    open("build/comp.js","w").write(data.replace("QWQWQ","").replace("zzHACK",""))

    # Parse it and remove undefined assignments.
    
    data = compress_common_names(data)
    
    open("build/comp2.js","w").write(data.replace("zzHACK",""))
    
    data = compress_webgl_variables(original_data, data)

    # Remove assignments of the form this.x = undefined;
    for set_to_undef in re.findall("((this.)?[a-zA-Z0-9_$]*=void 0)", data):
        set_to_undef = set_to_undef[0]
        a,_,b = data.partition(set_to_undef)
        #print(a[-30:],_,b[:30])
        if a[-1] in ',;':
            data = a[:-1]+b
        else:
            if b[0] in ',;':
                data = a+b[1:]
            else:
                print("WARNING")
                data = a+b
            
    open("build/comp3.js","w").write(data.replace("zzHACK",""))

    
    #print("Original gzip size", 13*1024-int(os.popen("cat /tmp/out.js | gzip -9 | wc").read().split()[-1]))
    #print("Uglify gzip size", 13*1024-int(os.popen("cat build/comp.js | gzip -9 | wc").read().split()[-1]))
    #print("Props gzip size", 13*1024-int(os.popen("cat build/comp2.js | gzip -9 | wc").read().split()[-1]))
    #print("GL shader gzip size", 13*1024-int(os.popen("cat build/comp3.js | gzip -9 | wc").read().split()[-1]))

    ## Create the build file
    open('build/index.html',"w").write(open("src/webglx.html").read()[:-49]+"<script>"+open("build/comp3.js").read().replace("QWQWQ","").replace("zzHACK","")+"</script>")

    #used = int(os.popen("cp build/comp3.js build/webglx.html /tmp && advzip -i 1000 -4 -a /tmp/foo.zip /tmp/comp3.js /tmp/webglx.html && wc /tmp/foo.zip").read().split()[-2])
    used = int(os.popen("advzip -i 100 -4 -a build/submit.zip build/index.html && wc build/submit.zip").read().split()[-2])
    
    print("total free advzip", 13*1024-used)
    
    
    
if __name__ == "__main__":
    compress()
# 139

