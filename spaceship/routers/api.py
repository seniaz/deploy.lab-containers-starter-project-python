from fastapi import APIRouter

router = APIRouter()


@router.get('')
def hello_world() -> dict:
    return {'msg': 'Hello, World! — Student #14'}


@router.get('/matrix')
def matrix_multiply() -> dict:
    import numpy as np

    matrix_a = np.random.rand(10, 10)
    matrix_b = np.random.rand(10, 10)
    product = matrix_a @ matrix_b

    return {
        'matrix_a': matrix_a.tolist(),
        'matrix_b': matrix_b.tolist(),
        'product': product.tolist(),
    }
