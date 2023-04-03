FROM ubuntu

# Install dependencies for Nix
RUN apt-get update && apt-get install -y \
    xz-utils \
    curl \
    file \
    git \
    sudo \
    bzip2

# Download and install Nix
RUN curl -L https://nixos.org/nix/install | sh -s -- --daemon

# Enable Nix in the shell
RUN . /root/.nix-profile/etc/profile.d/nix.sh && \
    echo ". /root/.nix-profile/etc/profile.d/nix.sh" >> /root/.bashrc

# enable flakes and nix command
RUN mkdir -p ~/.config/nix && \
    echo "experimental-features = nix-command flakes" >> ~/.config/nix/nix.conf

CMD ["/bin/bash"]


