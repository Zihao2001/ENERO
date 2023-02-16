# -*- coding: utf-8 -*-
import tensorflow as tf
from tensorflow import keras
from keras import regularizers

class myModel(tf.keras.Model):
    def __init__(self, hparams, hidden_init_actor, kernel_init_actor):
        super(myModel, self).__init__()
        self.hparams = hparams

        # Define layers here
        # Message passing layer
        '''
        "Sequential" is a linear stack of layers that can be added one by one, and it's a common way to define neural
        network architectures in Keras.
        '''
        self.Message = tf.keras.models.Sequential()
        self.Message.add(keras.layers.Dense(self.hparams['link_state_dim'],
                                            kernel_initializer=hidden_init_actor,
                                            activation=tf.nn.selu, name="FirstLayer"))
        # GRU-based update layer
        self.Update = tf.keras.layers.GRUCell(self.hparams['link_state_dim'], dtype=tf.float32)
        # Multi-layer perceptron readout layer
        self.Readout = tf.keras.models.Sequential()
        self.Readout.add(keras.layers.Dense(self.hparams['readout_units'],
                                            activation=tf.nn.selu,
                                            kernel_initializer=hidden_init_actor,
                                            kernel_regularizer=regularizers.l2(hparams['l2']),
                                            name="Readout1"))
        #self.Readout.add(keras.layers.Dropout(rate=hparams['dropout_rate']))
        self.Readout.add(keras.layers.Dense(self.hparams['readout_units'],
                                            activation=tf.nn.selu,
                                            kernel_initializer=hidden_init_actor,
                                            kernel_regularizer=regularizers.l2(hparams['l2']),
                                            name="Readout2"))
        #self.Readout.add(keras.layers.Dropout(rate=hparams['dropout_rate']))
        self.Readout.add(keras.layers.Dense(1, kernel_initializer=kernel_init_actor, name="Readout3"))

    def build(self, input_shape=None):
        # Creates the weights of the layers based on the input shapes
        # TensorShape is used to define the input shape of layers
        self.Message.build(input_shape=tf.TensorShape([None, self.hparams['link_state_dim']*2]))
        self.Update.build(input_shape=tf.TensorShape([None,self.hparams['link_state_dim']]))
        self.Readout.build(input_shape=[None, self.hparams['link_state_dim']])
        self.built = True # Set a flag indicating that the model has been built.

    #@tf.function
    def call(self, link_state, states_graph_ids, states_first, states_second, sates_num_edges, training=False):
        # Define the forward pass through the neural network.
        # Execute T times
        for _ in range(self.hparams['T']):
            '''
            These lines gather the hidden state of the main edge and its neighboring edges, concatenate them along
            the feature dimension, and store the concatenated tensor in edgesConcat.
            '''
            mainEdges = tf.gather(link_state, states_first)
            neighEdges = tf.gather(link_state, states_second)
            edgesConcat = tf.concat([mainEdges, neighEdges], axis=1)
            ### 1.a Message passing for link with all it's neighbours
            outputs = self.Message(edgesConcat)
            ### 1.b Sum of output values according to link id index
            edges_inputs = tf.math.unsorted_segment_sum(data=outputs, segment_ids=states_second,
                                                        num_segments=sates_num_edges)
            ### 2. Update for each link
            # GRUcell needs a 3D tensor as state because there is a matmul: Wrap the link state
            outputs, links_state_list = self.Update(edges_inputs, [link_state])
            link_state = links_state_list[0] # update the state of link_state from the previous step.
        # Perform sum of all hidden states
        edges_combi_outputs = tf.math.segment_sum(link_state, states_graph_ids, name=None)

        r = self.Readout(edges_combi_outputs,training=training)
        return r
