FROM continuumio/miniconda3:latest

WORKDIR /app

# repo cloned into /app dir, via the period at the end
RUN git clone https://github.com/uvaKCCI/flimanalyzer.git .

RUN conda install -c conda-forge mamba -y

RUN mamba env create -f environment.yml

#RUN conda env create -f environment.yml

# copy the line to activate the flim conda environment into .bashrc
# .bashrc is script that will automatically run when image is open, so the environment will be activated when image is open
RUN echo "conda activate flimenv-0.4.0" >> ~/.bashrc

# Subsequent run commands executed in bash shell
SHELL ["/bin/bash", "--login", "-c"]

RUN python setup.py install

ENV PREFECT__FLOWS__CHECKPOINTING=true

CMD ["flimanalyzer"]

