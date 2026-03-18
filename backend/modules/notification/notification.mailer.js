import nodemailer from 'nodemailer';

class NotificationMailer {
  constructor({ smtpConfig, mailFrom }) {
    this.smtpConfig = smtpConfig;
    this.mailFrom = mailFrom;
    this.transporter = nodemailer.createTransport({
      host: smtpConfig.host,
      port: smtpConfig.port,
      secure: smtpConfig.secure,
      auth: smtpConfig.user && smtpConfig.pass ? {
        user: smtpConfig.user,
        pass: smtpConfig.pass,
      } : undefined,
    });
  }

  async sendVerificationEmail({ to, username, verificationUrl }) {
    if (!to || !verificationUrl) {
      throw new Error('Email recipient and verification URL are required');
    }

    const text = [
      `Hello ${username},`,
      '',
      'Please verify your email address by opening the link below:',
      verificationUrl,
      '',
      'This link expires in 1 hour.',
      '',
      'If you did not create this account, ignore this email.',
    ].join('\n');

    const html = `
      <p>Hello ${username},</p>
      <p>Please verify your email address by opening the link below:</p>
      <p><a href="${verificationUrl}">Verify Email</a></p>
      <p>This link expires in 1 hour.</p>
      <p>If you did not create this account, ignore this email.</p>
    `;

    await this.transporter.sendMail({
      from: this.mailFrom,
      to,
      subject: 'Verify your Greenhouse account email',
      text,
      html,
    });
  }
}

export default NotificationMailer;

