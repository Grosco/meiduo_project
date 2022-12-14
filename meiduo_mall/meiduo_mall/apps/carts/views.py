import base64
import pickle
import json

from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views import View

from django_redis import get_redis_connection

from carts import constants
from goods.models import SKU
from meiduo_mall.utils.response_code import RETCODE


# Create your views here.
class CartsView(View):
    """
    参数名 	类型 	是否必传 	说明
    sku_id 	int 	是 	商品SKU编号
    count 	int 	是 	商品数量
    selected 	bool 	否 	是否勾选
    """

    def get(self, request, simple=None):
        user = request.user
        if user.is_authenticated:
            # 用户已登录，查询redis购物车
            redis_conn = get_redis_connection('carts')
            carts_redis = redis_conn.hgetall(f'carts_{user.id}')
            selected_redis = redis_conn.smembers(f'selected_{user.id}')
            carts_dict = {}
            for sku_id, count in carts_redis.items():
                carts_dict[int(sku_id.decode())] = {
                    'count': int(count.decode()),
                    'selected': sku_id in selected_redis,
                }
        else:
            # 用户未登录，查询cookies购物车
            carts_str = request.COOKIES.get('carts')
            # 如果用户操作过cookie购物车
            if carts_str:
                # 将cart_str转成bytes,再将bytes转成base64的bytes,最后将bytes转字典
                carts_dict = pickle.loads(base64.b64decode(carts_str.encode()))
            # 用户从没有操作过cookie购物车
            else:
                carts_dict = {}
            carts_dict_ = {}
            for key, value in carts_dict.items():
                carts_dict_[int(key)] = value
            carts_dict = carts_dict_
        # 购物车渲染数据
        sku_ids = carts_dict.keys()
        skus = SKU.objects.filter(id__in=sku_ids)
        cart_skus = []
        for sku in skus:
            sku_count = carts_dict.get(sku.id).get('count')
            sku_dict = {
                'id': sku.id,
                'name': sku.name,
                'count': sku_count,
                'selected': str(carts_dict.get(sku.id).get('selected')),
                'default_image': sku.default_image,
                'price': str(sku.price),
                'amount': str(sku.price * sku_count),
            }
            cart_skus.append(sku_dict)
        if not simple:
            context = {
                'cart_skus': cart_skus,
            }
            return render(request, 'cart.html', context=context)
        elif simple == 'simple':
            return JsonResponse({'code': RETCODE.OK, 'errmsg': '简单购物车', 'cart_skus': cart_skus})

    def post(self, request):
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')
        count = json_dict.get('count')
        selected = json_dict.get('selected', True)

        required = [sku_id, count]
        if not all(required):
            return HttpResponseForbidden('缺少必传参数')
        try:
            SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            return HttpResponseForbidden('商品不存在')
        try:
            count = int(count)
        except Exception:
            return HttpResponseForbidden('参数count有误')
        if not isinstance(selected, bool):
            return HttpResponseForbidden('参数selected有误')

        user = request.user
        if user.is_authenticated:
            # 用户已登录，操作redis购物车
            redis_conn = get_redis_connection('carts')
            redis_pipeline = redis_conn.pipeline()
            redis_pipeline.hincrby(f'carts_{user.id}', sku_id, count)
            if selected:
                redis_pipeline.sadd(f'selected_{user.id}', sku_id)
            redis_pipeline.execute()
            return JsonResponse({'code': RETCODE.OK, 'errmsg': '添加购物车成功'})
        else:
            # 用户未登录，操作cookie购物车
            carts_str = request.COOKIES.get('carts')
            # 如果用户操作过cookie购物车
            if carts_str:
                # 将cart_str转成bytes,再将bytes转成base64的bytes,最后将bytes转字典
                carts_dict = pickle.loads(base64.b64decode(carts_str.encode()))
            # 用户从没有操作过cookie购物车
            else:
                carts_dict = {}
            carts_dict_ = {}
            for key, value in carts_dict.items():
                carts_dict_[int(key)] = value
            carts_dict = carts_dict_
            # 判断要加入购物车的商品是否已经在购物车中,如有相同商品，累加求和，反之，直接赋值
            if int(sku_id) in carts_dict.keys():
                origin_count = carts_dict[int(sku_id)]['count']
                count += origin_count
            carts_dict[sku_id] = {
                'count': count,
                'selected': selected,
            }
            # 将字典转成bytes,再将bytes转成base64的bytes,最后将bytes转字符串
            cookie_carts_str = base64.b64encode(pickle.dumps(carts_dict)).decode()
            response = JsonResponse({'code': RETCODE.OK, 'errmsg': '添加购物车成功'})
            response.set_cookie('carts', cookie_carts_str, max_age=constants.CARTS_COOKIE_EXPIRES)
            return response

    def put(self, request, select_all=None):
        json_dict = json.loads(request.body.decode())
        selected = bool(json_dict.get('selected'))

        if select_all is None:
            sku_id = json_dict.get('sku_id')
            count = json_dict.get('count')

            required = [sku_id, count]
            if not all(required):
                return HttpResponseForbidden('缺少必传参数')
            try:
                sku = SKU.objects.get(id=sku_id)
            except SKU.DoesNotExist:
                return HttpResponseForbidden('商品不存在')
            try:
                count = int(count)
            except Exception:
                return HttpResponseForbidden('参数count有误')
            if not isinstance(selected, bool):
                return HttpResponseForbidden('参数selected有误')

            user = request.user
            if user.is_authenticated:
                # 用户已登录，操作redis购物车
                redis_conn = get_redis_connection('carts')
                try:
                    int(redis_conn.hget(f'carts_{user.id}', sku_id).decode())
                except Exception:
                    return HttpResponseForbidden('用户或商品id不存在')
                redis_pipeline = redis_conn.pipeline()
                redis_pipeline.hset(f'carts_{user.id}', sku_id, count)
                if selected:
                    redis_pipeline.sadd(f'selected_{user.id}', sku_id)
                else:
                    redis_pipeline.srem(f'selected_{user.id}', sku_id)
                redis_pipeline.execute()

                cart_sku = {
                    'id': sku_id,
                    'name': sku.name,
                    'count': count,
                    'selected': str(selected),
                    'default_image': sku.default_image,
                    'price': str(sku.price),
                    'amount': str(sku.price * count),
                }
                return JsonResponse({'code': RETCODE.OK, 'errmsg': '修改购物车成功', 'cart_sku': cart_sku})
            else:
                # 用户未登录，操作cookie购物车
                carts_str = request.COOKIES.get('carts')
                if carts_str:
                    # 将cart_str转成bytes,再将bytes转成base64的bytes,最后将bytes转字典
                    carts_dict = pickle.loads(base64.b64decode(carts_str.encode()))
                else:
                    return HttpResponseForbidden('cookie购物车数据不存在')
                carts_dict_ = {}
                for key, value in carts_dict.items():
                    carts_dict_[int(key)] = value
                carts_dict = carts_dict_
                if sku_id in carts_dict:
                    carts_dict[sku_id] = {
                        'count': count,
                        'selected': selected,
                    }
                else:
                    return HttpResponseForbidden('商品id不存在')
                # 响应数据
                cart_sku = {
                    'id': sku_id,
                    'name': sku.name,
                    'count': count,
                    'selected': selected,
                    'default_image': sku.default_image,
                    'price': str(sku.price),
                    'amount': str(sku.price * count),
                }
                # cookie数据
                cookie_carts_str = base64.b64encode(pickle.dumps(carts_dict)).decode()
                response = JsonResponse({'code': RETCODE.OK, 'errmsg': '添加购物车成功', 'cart_sku': cart_sku})
                response.set_cookie('carts', cookie_carts_str, max_age=constants.CARTS_COOKIE_EXPIRES)
                return response
        elif select_all == 'selectall':
            if not isinstance(selected, bool):
                return HttpResponseForbidden('参数selected有误')

            user = request.user
            if user.is_authenticated:
                # 用户已登录，操作redis购物车
                redis_conn = get_redis_connection('carts')
                sku_ids = redis_conn.hkeys(f'carts_{user.id}')
                if len(sku_ids) > 0:
                    if selected:
                        redis_conn.sadd(f'selected_{user.id}', *sku_ids)
                        return JsonResponse({'code': RETCODE.OK, 'errmsg': '全选购物车成功'})
                    else:
                        redis_conn.srem(f'selected_{user.id}', *sku_ids)
                        return JsonResponse({'code': RETCODE.OK, 'errmsg': '取消全选购物车成功'})
                else:
                    return JsonResponse({'code': RETCODE.OK, 'errmsg': '购物车为空'})

            else:
                # 用户未登录，操作cookie购物车
                carts_str = request.COOKIES.get('carts')
                if carts_str:
                    # 将cart_str转成bytes,再将bytes转成base64的bytes,最后将bytes转字典
                    carts_dict = pickle.loads(base64.b64decode(carts_str.encode()))
                else:
                    return HttpResponseForbidden('cookie购物车数据不存在')
                carts_dict_ = {}
                for key, value in carts_dict.items():
                    carts_dict_[int(key)] = value
                carts_dict = carts_dict_
                for sku_id in carts_dict:
                    carts_dict[sku_id]['selected'] = selected,

                # cookie数据
                cookie_carts_str = base64.b64encode(pickle.dumps(carts_dict)).decode()
                response = JsonResponse({'code': RETCODE.OK, 'errmsg': '全选购物车成功'})
                response.set_cookie('carts', cookie_carts_str, max_age=constants.CARTS_COOKIE_EXPIRES)
                return response

    def delete(self, request):
        json_dict = json.loads(request.body.decode())
        sku_id = json_dict.get('sku_id')

        required = [sku_id, ]
        if not all(required):
            return HttpResponseForbidden('缺少必传参数')
        try:
            sku = SKU.objects.get(id=sku_id)
        except SKU.DoesNotExist:
            return HttpResponseForbidden('商品不存在')

        user = request.user
        if user.is_authenticated:
            # 用户已登录，操作redis购物车
            redis_conn = get_redis_connection('carts')
            try:
                int(redis_conn.hget(f'carts_{user.id}', sku_id).decode())
            except Exception:
                return HttpResponseForbidden('用户或商品id不存在')
            redis_pipeline = redis_conn.pipeline()
            redis_pipeline.hdel(f'carts_{user.id}', sku_id)
            redis_pipeline.srem(f'selected_{user.id}', sku_id)
            redis_pipeline.execute()

            return JsonResponse({'code': RETCODE.OK, 'errmsg': '购物车删除商品成功'})
        else:
            # 用户未登录，操作cookie购物车
            carts_str = request.COOKIES.get('carts')
            if carts_str:
                # 将cart_str转成bytes,再将bytes转成base64的bytes,最后将bytes转字典
                carts_dict = pickle.loads(base64.b64decode(carts_str.encode()))
            else:
                return HttpResponseForbidden('cookie购物车数据不存在')
            carts_dict_ = {}
            for key, value in carts_dict.items():
                carts_dict_[int(key)] = value
            carts_dict = carts_dict_
            if sku_id in carts_dict:
                carts_dict.pop(sku_id)
            else:
                return HttpResponseForbidden('商品id不存在')
            # cookie数据
            cookie_carts_str = base64.b64encode(pickle.dumps(carts_dict)).decode()
            response = JsonResponse({'code': RETCODE.OK, 'errmsg': '删除购物车成功'})
            response.set_cookie('carts', cookie_carts_str, max_age=constants.CARTS_COOKIE_EXPIRES)
            return response
