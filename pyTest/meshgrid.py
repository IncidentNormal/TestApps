import numpy as np

def get_test_data(delta=0.05):
    '''
    Return a tuple X, Y, Z with a test data set.
    '''

    from matplotlib.mlab import  bivariate_normal
    x = y = np.arange(-3.0, 3.0, delta)
    print x
    X, Y = np.meshgrid(x, y)

    Z = np.sin(X)
    print Z
##    Z1 = bivariate_normal(X, Y, 1.0, 1.0, 0.0, 0.0)
##
##    Z2 = bivariate_normal(X, Y, 1.5, 0.5, 1, 1)
##
##    Z = Z2 - Z1
##    #print 'Z'
##    #print Z[0]
##    #print Z[0][0]

    X = X * 10
    Y = Y * 10
    Z = Z * 500
    return X, Y, Z

get_test_data()
